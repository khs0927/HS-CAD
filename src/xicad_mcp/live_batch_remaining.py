from __future__ import annotations

import hashlib
import json
from math import pi, radians
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import MultiplicationRequest, MultiplicationResult, multiply_numbers
from .headless_core_batch2 import (
    ExistingStylePolicy,
    SectionMarkMode,
    SectionMarkPlan,
    SectionMarkRequest,
    TableStyleAction,
    TableStylePlan,
    TableStyleRequest,
    TableStyleSnapshot,
    TableStyleSpec,
    plan_section_mark,
    plan_table_style,
)
from .headless_core_batch3 import (
    ToiletBoothLegacyVariant,
    ToiletBoothPlan,
    ToiletBoothRequest,
    plan_toilet_booth,
)


class CadFreeMultiplicationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result: MultiplicationResult
    production_usable: bool = True


class LiveToiletBoothPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_name: str = Field(min_length=1)
    booth: ToiletBoothRequest

    @model_validator(mode="after")
    def validate_live_request(self) -> LiveToiletBoothPreviewRequest:
        if self.booth.document_id.casefold() != self.document_name.casefold():
            raise ValueError("booth document_id must match document_name")
        if not self.booth.dry_run:
            raise ValueError("live preview requires the headless booth request in dry-run mode")
        return self

    def fingerprint(self) -> str:
        return _fingerprint(self.model_dump(mode="json"))


class LiveToiletBoothExecuteRequest(LiveToiletBoothPreviewRequest):
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _fingerprint(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveSectionMarkPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_name: str = Field(min_length=1)
    section: SectionMarkRequest

    @model_validator(mode="after")
    def validate_live_request(self) -> LiveSectionMarkPreviewRequest:
        if self.section.document_id.casefold() != self.document_name.casefold():
            raise ValueError("section document_id must match document_name")
        if not self.section.dry_run:
            raise ValueError("live preview requires the headless section request in dry-run mode")
        return self

    def fingerprint(self) -> str:
        return _fingerprint(self.model_dump(mode="json"))


class LiveSectionMarkExecuteRequest(LiveSectionMarkPreviewRequest):
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _fingerprint(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class CreatedEntityEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    handle: str
    expected_object_name: str
    present: bool
    type_matches: bool


class LiveGeometryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_name: str
    command_alias: str
    created_handles: tuple[str, ...]
    evidence: tuple[CreatedEntityEvidence, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


class LiveTableStylePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_name: str = Field(min_length=1)
    desired: TableStyleSpec
    existing_policy: ExistingStylePolicy


class LiveTableStyleExecuteRequest(LiveTableStylePreviewRequest):
    expected_existing: TableStyleSnapshot
    expected_action: TableStyleAction
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _fingerprint(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveTableStyleResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_name: str
    style_name: str
    action: TableStyleAction
    changed: bool
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


def execute_cad_free_multiplication(request: MultiplicationRequest) -> CadFreeMultiplicationResult:
    return CadFreeMultiplicationResult(result=multiply_numbers(request))


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _drawing(document_name: str) -> Any:
    import win32com.client

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == document_name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {document_name!r}, found {len(matches)}")
    doc = matches[0]
    doc.Activate()
    return doc


def _require_named_item(collection: Any, name: str, kind: str) -> Any:
    try:
        return collection.Item(name)
    except Exception as exc:
        raise ValueError(f"{kind} not found: {name}") from exc


def _point(point: Any) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        [float(point.x), float(point.y), float(point.z)],
    )


def _objects_by_handle(doc: Any) -> dict[str, Any]:
    return {str(entity.Handle).casefold(): entity for entity in doc.ModelSpace}


def _create_line(doc: Any, spec: Any) -> Any:
    entity = doc.ModelSpace.AddLine(_point(spec.start), _point(spec.end))
    entity.Layer = spec.layer
    return entity


def _create_arc(doc: Any, spec: Any) -> Any:
    # ActiveX arcs are counter-clockwise. xiCAD booth arcs describe a 90-degree
    # geometric sweep, so reverse negative sweeps to preserve the same arc set.
    delta = (spec.end_angle_degrees - spec.start_angle_degrees + 180.0) % 360.0 - 180.0
    if delta >= 0:
        start, end = spec.start_angle_degrees, spec.start_angle_degrees + delta
    else:
        start, end = spec.start_angle_degrees + delta, spec.start_angle_degrees
    entity = doc.ModelSpace.AddArc(_point(spec.center), spec.radius, radians(start) % (2 * pi), radians(end) % (2 * pi))
    entity.Layer = spec.layer
    return entity


def _geometry_evidence(doc: Any, created: list[tuple[Any, str]]) -> tuple[CreatedEntityEvidence, ...]:
    after = _objects_by_handle(doc)
    return tuple(
        CreatedEntityEvidence(
            handle=str(entity.Handle),
            expected_object_name=expected,
            present=str(entity.Handle).casefold() in after,
            type_matches=str(entity.ObjectName).casefold() == expected.casefold(),
        )
        for entity, expected in created
    )


def preview_live_toilet_booth(request: LiveToiletBoothPreviewRequest) -> dict[str, Any]:
    doc = _drawing(request.document_name)
    _require_named_item(doc.Layers, request.booth.layer, "layer")
    plan = plan_toilet_booth(request.booth)
    return {
        **request.model_dump(mode="json"),
        "command_alias": plan.command_alias,
        "entity_count": len(plan.wall_lines) + len(plan.door_leaf_lines) + len(plan.door_swing_arcs),
        "approval_fingerprint": request.fingerprint(),
        "mutation": True,
    }


def execute_live_toilet_booth(
    request: LiveToiletBoothExecuteRequest,
    *,
    allowed_variant: ToiletBoothLegacyVariant | None = None,
) -> LiveGeometryResult:
    if allowed_variant is not None and request.booth.legacy_variant is not allowed_variant:
        raise ValueError(f"this tool only executes {allowed_variant}")
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact MTB request")
    doc = _drawing(request.document_name)
    _require_named_item(doc.Layers, request.booth.layer, "layer")
    plan: ToiletBoothPlan = plan_toilet_booth(request.booth)
    created: list[tuple[Any, str]] = []
    opened = False
    closed = False
    try:
        doc.StartUndoMark()
        opened = True
        for spec in (*plan.wall_lines, *plan.door_leaf_lines):
            created.append((_create_line(doc, spec), "AcDbLine"))
        for spec in plan.door_swing_arcs:
            created.append((_create_arc(doc, spec), "AcDbArc"))
    finally:
        if opened:
            doc.EndUndoMark()
            closed = True
    evidence = _geometry_evidence(doc, created)
    if not evidence or not all(item.present and item.type_matches for item in evidence):
        raise RuntimeError("MTB postcondition failed")
    return LiveGeometryResult(
        document_name=str(doc.Name),
        command_alias=plan.command_alias,
        created_handles=tuple(item.handle for item in evidence),
        evidence=evidence,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
        postcondition_verified=True,
    )


def execute_live_mtb1(request: LiveToiletBoothExecuteRequest) -> LiveGeometryResult:
    return execute_live_toilet_booth(request, allowed_variant=ToiletBoothLegacyVariant.MTB1)


def execute_live_mtb2(request: LiveToiletBoothExecuteRequest) -> LiveGeometryResult:
    return execute_live_toilet_booth(request, allowed_variant=ToiletBoothLegacyVariant.MTB2)


def preview_live_section_mark(request: LiveSectionMarkPreviewRequest) -> dict[str, Any]:
    doc = _drawing(request.document_name)
    _require_named_item(doc.Layers, request.section.layer, "layer")
    _require_named_item(doc.TextStyles, request.section.text_style, "text style")
    plan = plan_section_mark(request.section)
    return {
        **request.model_dump(mode="json"),
        "command_alias": plan.command_alias,
        "entity_count": len(plan.cut_lines) + len(plan.tail_lines) + len(plan.labels),
        "approval_fingerprint": request.fingerprint(),
        "mutation": True,
    }


def execute_live_section_mark(
    request: LiveSectionMarkExecuteRequest,
    *,
    allowed_mode: SectionMarkMode | None = None,
) -> LiveGeometryResult:
    if allowed_mode is not None and request.section.mode is not allowed_mode:
        alias = "SCC" if allowed_mode is SectionMarkMode.SINGLE else "SCD"
        raise ValueError(f"this tool only executes {alias}")
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact section-mark request")
    doc = _drawing(request.document_name)
    _require_named_item(doc.Layers, request.section.layer, "layer")
    _require_named_item(doc.TextStyles, request.section.text_style, "text style")
    plan: SectionMarkPlan = plan_section_mark(request.section)
    created: list[tuple[Any, str]] = []
    opened = False
    closed = False
    try:
        doc.StartUndoMark()
        opened = True
        for spec in (*plan.cut_lines, *plan.tail_lines):
            created.append((_create_line(doc, spec), "AcDbLine"))
        for spec in plan.labels:
            text = doc.ModelSpace.AddText(spec.text, _point(spec.insertion_point), spec.text_height)
            text.Layer = spec.layer
            text.StyleName = spec.text_style
            text.Rotation = radians(spec.rotation_degrees)
            created.append((text, "AcDbText"))
    finally:
        if opened:
            doc.EndUndoMark()
            closed = True
    evidence = _geometry_evidence(doc, created)
    if not evidence or not all(item.present and item.type_matches for item in evidence):
        raise RuntimeError("section-mark postcondition failed")
    return LiveGeometryResult(
        document_name=str(doc.Name),
        command_alias=plan.command_alias,
        created_handles=tuple(item.handle for item in evidence),
        evidence=evidence,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
        postcondition_verified=True,
    )


def execute_live_scc(request: LiveSectionMarkExecuteRequest) -> LiveGeometryResult:
    return execute_live_section_mark(request, allowed_mode=SectionMarkMode.SINGLE)


def execute_live_scd(request: LiveSectionMarkExecuteRequest) -> LiveGeometryResult:
    return execute_live_section_mark(request, allowed_mode=SectionMarkMode.DOUBLE)


def _table_style_dictionary(doc: Any) -> Any:
    return _require_named_item(doc.Dictionaries, "ACAD_TABLESTYLE", "table-style dictionary")


def _read_table_style(doc: Any, name: str) -> TableStyleSnapshot:
    dictionary = _table_style_dictionary(doc)
    try:
        style = dictionary.Item(name)
    except Exception:
        return TableStyleSnapshot(exists=False)
    flow = "down" if int(style.FlowDirection) == 0 else "up"
    return TableStyleSnapshot(
        exists=True,
        spec=TableStyleSpec(
            style_name=name,
            title_text_style=str(style.GetTextStyle(1)),
            header_text_style=str(style.GetTextStyle(2)),
            data_text_style=str(style.GetTextStyle(4)),
            title_text_height=float(style.GetTextHeight(1)),
            header_text_height=float(style.GetTextHeight(2)),
            data_text_height=float(style.GetTextHeight(4)),
            horizontal_cell_margin=float(style.HorzCellMargin),
            vertical_cell_margin=float(style.VertCellMargin),
            flow_direction=flow,
        ),
    )


def _apply_table_style(style: Any, spec: TableStyleSpec) -> None:
    style.SetTextStyle(1, spec.title_text_style)
    style.SetTextStyle(2, spec.header_text_style)
    style.SetTextStyle(4, spec.data_text_style)
    style.SetTextHeight(1, spec.title_text_height)
    style.SetTextHeight(2, spec.header_text_height)
    style.SetTextHeight(4, spec.data_text_height)
    style.HorzCellMargin = spec.horizontal_cell_margin
    style.VertCellMargin = spec.vertical_cell_margin
    style.FlowDirection = 0 if spec.flow_direction == "down" else 1


def _table_plan(request: LiveTableStylePreviewRequest, existing: TableStyleSnapshot) -> TableStylePlan:
    return plan_table_style(
        TableStyleRequest(
            document_id=request.document_name,
            desired=request.desired,
            existing_policy=request.existing_policy,
        ),
        existing,
    )


def preview_live_table_style(request: LiveTableStylePreviewRequest) -> dict[str, Any]:
    doc = _drawing(request.document_name)
    for style_name in {
        request.desired.title_text_style,
        request.desired.header_text_style,
        request.desired.data_text_style,
    }:
        _require_named_item(doc.TextStyles, style_name, "text style")
    existing = _read_table_style(doc, request.desired.style_name)
    plan = _table_plan(request, existing)
    payload = {
        **request.model_dump(mode="json"),
        "expected_existing": existing.model_dump(mode="json"),
        "expected_action": plan.action.value,
    }
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": plan.action in {TableStyleAction.CREATE, TableStyleAction.UPDATE},
    }


def execute_live_table_style(request: LiveTableStyleExecuteRequest) -> LiveTableStyleResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact TBM request")
    doc = _drawing(request.document_name)
    for style_name in {
        request.desired.title_text_style,
        request.desired.header_text_style,
        request.desired.data_text_style,
    }:
        _require_named_item(doc.TextStyles, style_name, "text style")
    existing = _read_table_style(doc, request.desired.style_name)
    plan = _table_plan(request, existing)
    if existing != request.expected_existing or plan.action is not request.expected_action:
        raise ValueError("table-style state no longer matches the approved plan")
    opened = False
    closed = False
    changed = plan.action in {TableStyleAction.CREATE, TableStyleAction.UPDATE}
    if changed:
        try:
            doc.StartUndoMark()
            opened = True
            dictionary = _table_style_dictionary(doc)
            style = (
                dictionary.AddObject(request.desired.style_name, "AcDbTableStyle")
                if plan.action is TableStyleAction.CREATE
                else dictionary.Item(request.desired.style_name)
            )
            _apply_table_style(style, request.desired)
        finally:
            if opened:
                doc.EndUndoMark()
                closed = True
    after = _read_table_style(doc, request.desired.style_name)
    expected_after = request.desired if changed else existing.spec
    if not after.exists or after.spec != expected_after:
        raise RuntimeError("TBM postcondition failed")
    return LiveTableStyleResult(
        document_name=str(doc.Name),
        style_name=request.desired.style_name,
        action=plan.action,
        changed=changed,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
        postcondition_verified=True,
    )


def register_live_remaining_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD geometry/style mutation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD geometry/style mutation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    cad_free = ToolAnnotations(
        title="Execute CAD-free xiCAD multiplication",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_execute_cad_free_multiplication", execute_cad_free_multiplication, cad_free),
        ("xicad_preview_live_toilet_booth", preview_live_toilet_booth, preview),
        ("xicad_execute_live_mtb1", execute_live_mtb1, execute),
        ("xicad_execute_live_mtb2", execute_live_mtb2, execute),
        ("xicad_preview_live_section_mark", preview_live_section_mark, preview),
        ("xicad_execute_live_scc", execute_live_scc, execute),
        ("xicad_execute_live_scd", execute_live_scd, execute),
        ("xicad_preview_live_table_style", preview_live_table_style, preview),
        ("xicad_execute_live_table_style", execute_live_table_style, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
