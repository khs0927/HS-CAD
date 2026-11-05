from __future__ import annotations

import hashlib
import json
from math import degrees, radians
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch5 import DrawingSpace, TextEntityKind, TextEntitySnapshot
from .headless_core_batch7 import (
    FieldTextSnapshot,
    FieldToTextRequest,
    FindMarkRequest,
    JustificationRequest,
    MarkShape,
    PartialTextCopyRequest,
    SearchMode,
    SourceDisposition,
    StyleScope,
    TextJustification,
    TextStyleRequest,
    TextToMTextRequest,
    UnresolvedFieldPolicy,
    plan_field_to_text,
    plan_find_and_mark,
    plan_justification,
    plan_partial_text_copy,
    plan_text_style,
    plan_text_to_mtext,
)


def _hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _models(items: tuple[BaseModel, ...]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in items]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)


class LiveFamPreviewRequest(_Request):
    query: str = Field(min_length=1)
    target_handles: tuple[str, ...] | None = None
    mode: SearchMode
    ignore_spaces: bool = False
    case_sensitive: bool = False
    whole_string: bool = False
    allowed_kinds: tuple[TextEntityKind, ...] = tuple(TextEntityKind)
    exclude_locked_layers: bool = True
    mark_shape: MarkShape | None = None
    mark_layer: str | None = None
    circle_radius: float | None = Field(default=None, gt=0)
    block_name: str | None = None
    mark_insertion_point: bool = False


class LiveFamExecuteRequest(LiveFamPreviewRequest):
    expected_entities: tuple[TextEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveFieldResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    handle: str = Field(min_length=1)
    field_expression: str = Field(min_length=1)
    evaluated_text: str | None = None
    literal_fallback: str | None = None


class LiveFttPreviewRequest(_Request):
    resolutions: tuple[LiveFieldResolution, ...] = Field(min_length=1)
    unresolved_policy: UnresolvedFieldPolicy


class LiveFttExecuteRequest(LiveFttPreviewRequest):
    expected_fields: tuple[FieldTextSnapshot, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveT2mPreviewRequest(_Request):
    target_handles: tuple[str, ...] = Field(min_length=1)
    source_disposition: SourceDisposition
    preserve_visual_width: bool


class LiveT2mExecuteRequest(LiveT2mPreviewRequest):
    expected_entities: tuple[TextEntitySnapshot, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveTecPreviewRequest(_Request):
    target_handles: tuple[str, ...] = Field(min_length=1)
    mode: str = Field(pattern=r"^(slice|regex_group)$")
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    pattern: str | None = None
    group: int = Field(default=0, ge=0)


class LiveTecExecuteRequest(LiveTecPreviewRequest):
    expected_entities: tuple[TextEntitySnapshot, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveTjPreviewRequest(_Request):
    target_handles: tuple[str, ...] = Field(min_length=1)
    justification: TextJustification
    preserve_visual_position: bool


class LiveTjExecuteRequest(LiveTjPreviewRequest):
    expected_entities: tuple[TextEntitySnapshot, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveTsaPreviewRequest(_Request):
    target_style: str = Field(min_length=1)
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)
    allowed_kinds: tuple[TextEntityKind, ...] = (
        TextEntityKind.TEXT,
        TextEntityKind.MTEXT,
        TextEntityKind.ATTRIB,
        TextEntityKind.ATTDEF,
    )


class LiveTsaExecuteRequest(LiveTsaPreviewRequest):
    expected_entities: tuple[TextEntitySnapshot, ...]
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _hash(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LiveText7aResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: str
    matched_handles: tuple[str, ...] = ()
    changed_handles: tuple[str, ...] = ()
    created_handles: tuple[str, ...] = ()
    erased_handles: tuple[str, ...] = ()
    extracted_values: tuple[str, ...] = ()
    postcondition_verified: bool


class ZWCADLiveText7aAdapter:
    _KINDS = {
        "acdbtext": TextEntityKind.TEXT,
        "acdbmtext": TextEntityKind.MTEXT,
        "acdbattribute": TextEntityKind.ATTRIB,
        "acdbattributedefinition": TextEntityKind.ATTDEF,
    }

    def __init__(self, document_name: str) -> None:
        self.document_name = document_name
        self.app: Any | None = None
        self.doc: Any | None = None

    def connect(self) -> Any:
        if self.doc is not None:
            return self.doc
        import win32com.client

        self.app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
        matches = [doc for doc in self.app.Documents if str(doc.Name).casefold() == self.document_name.casefold()]
        if len(matches) != 1:
            raise RuntimeError(f"expected exactly one open document named {self.document_name!r}, found {len(matches)}")
        self.doc = matches[0]
        self.doc.Activate()
        return self.doc

    def _spaces(self) -> tuple[tuple[DrawingSpace, Any], ...]:
        doc = self.connect()
        result: list[tuple[DrawingSpace, Any]] = [(DrawingSpace.MODEL, doc.ModelSpace)]
        result.extend(
            (DrawingSpace.PAPER, layout.Block) for layout in doc.Layouts if str(layout.Name).casefold() != "model"
        )
        return tuple(result)

    def objects(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for _space, owner in self._spaces():
            for entity in owner:
                result[str(entity.Handle).casefold()] = entity
        return result

    def entity(self, handle: str) -> Any:
        entity = self.objects().get(handle.casefold())
        if entity is None:
            raise ValueError(f"text entity not found: {handle}")
        return entity

    def owner(self, handle: str) -> Any:
        for _space, owner in self._spaces():
            if any(str(entity.Handle).casefold() == handle.casefold() for entity in owner):
                return owner
        raise ValueError(f"entity owner not found: {handle}")

    def _locked(self, layer_name: str) -> bool:
        try:
            return bool(self.connect().Layers.Item(layer_name).Lock)
        except Exception as exc:
            raise RuntimeError(f"cannot determine layer lock state: {layer_name}") from exc

    @staticmethod
    def _point(value: Any) -> Point3D:
        coordinates = tuple(float(item) for item in value)
        if len(coordinates) != 3:
            raise RuntimeError("ZWCAD returned invalid text insertion point")
        return Point3D(x=coordinates[0], y=coordinates[1], z=coordinates[2])

    def snapshots(self, handles: tuple[str, ...] | None = None) -> tuple[TextEntitySnapshot, ...]:
        wanted = None if handles is None else {handle.casefold() for handle in handles}
        snapshots: list[TextEntitySnapshot] = []
        for space, owner in self._spaces():
            for entity in owner:
                handle = str(entity.Handle)
                if wanted is not None and handle.casefold() not in wanted:
                    continue
                kind = self._KINDS.get(str(entity.ObjectName).casefold())
                if kind is None:
                    continue
                layer = str(entity.Layer)
                snapshots.append(
                    TextEntitySnapshot(
                        handle=handle,
                        text=str(entity.TextString),
                        kind=kind,
                        layer=layer,
                        text_style=str(entity.StyleName),
                        text_height=float(entity.TextHeight if kind is TextEntityKind.MTEXT else entity.Height),
                        insertion_point=self._point(entity.InsertionPoint),
                        rotation_degrees=degrees(float(entity.Rotation)),
                        space=space,
                        locked_layer=self._locked(layer),
                        is_xref="|" in layer,
                    )
                )
        if wanted is not None and {item.handle.casefold() for item in snapshots} != wanted:
            missing = sorted(wanted - {item.handle.casefold() for item in snapshots})
            raise ValueError(f"unsupported or missing text handles: {missing}")
        snapshots.sort(key=lambda item: item.handle.casefold())
        return tuple(snapshots)

    def fields(self, resolutions: tuple[LiveFieldResolution, ...]) -> tuple[FieldTextSnapshot, ...]:
        snapshots = {item.handle.casefold(): item for item in self.snapshots(tuple(r.handle for r in resolutions))}
        result = []
        for resolution in resolutions:
            snapshot = snapshots[resolution.handle.casefold()]
            if snapshot.text != resolution.field_expression:
                raise ValueError(f"field expression precondition failed: {resolution.handle}")
            if "%<" not in snapshot.text or ">%" not in snapshot.text:
                raise ValueError(f"FTT target does not contain a field expression: {resolution.handle}")
            result.append(
                FieldTextSnapshot(
                    handle=snapshot.handle,
                    field_expression=snapshot.text,
                    evaluated_text=resolution.evaluated_text,
                    literal_fallback=resolution.literal_fallback,
                    locked_layer=snapshot.locked_layer,
                    is_xref=snapshot.is_xref,
                )
            )
        return tuple(result)

    def vector(self, point: Point3D) -> Any:
        import pythoncom
        import win32com.client

        return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [point.x, point.y, point.z])

    def bbox(self, entity: Any) -> tuple[Point3D, Point3D]:
        minimum, maximum = entity.GetBoundingBox()
        return self._point(minimum), self._point(maximum)


def _approval(execute: bool, fingerprint: str | None = None) -> Approval:
    return Approval(approved=execute, fingerprint=fingerprint)


def _ensure_same(actual: tuple[BaseModel, ...], expected: tuple[BaseModel, ...], alias: str) -> None:
    if _models(actual) != _models(expected):
        raise ValueError(f"{alias} entity preconditions no longer match the approved snapshots")


def _fam_core(request: LiveFamPreviewRequest, *, execute: bool, fingerprint: str | None = None) -> FindMarkRequest:
    return FindMarkRequest(
        document_id=request.document_name,
        query=request.query,
        target_handles=request.target_handles,
        mode=request.mode,
        ignore_spaces=request.ignore_spaces,
        case_sensitive=request.case_sensitive,
        whole_string=request.whole_string,
        allowed_kinds=request.allowed_kinds,
        exclude_locked_layers=request.exclude_locked_layers,
        mark_shape=request.mark_shape,
        mark_layer=request.mark_layer,
        circle_radius=request.circle_radius,
        block_name=request.block_name,
        mark_insertion_point=request.mark_insertion_point,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_fam(request: LiveFamPreviewRequest) -> dict[str, Any]:
    if request.mode is SearchMode.MARK and request.mark_shape in {MarkShape.BOX, MarkShape.LINE}:
        raise ValueError("FAM live BOX/LINE markers require geometry absent from the Batch 7 contract")
    adapter = ZWCADLiveText7aAdapter(request.document_name)
    entities = adapter.snapshots(request.target_handles)
    plan = plan_find_and_mark(_fam_core(request, execute=False), entities)
    payload = {**request.model_dump(mode="json"), "expected_entities": _models(entities)}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_fam(request: LiveFamExecuteRequest) -> LiveText7aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact FAM request")
    adapter = ZWCADLiveText7aAdapter(request.document_name)
    actual = adapter.snapshots(request.target_handles)
    _ensure_same(actual, request.expected_entities, "FAM")
    plan = plan_find_and_mark(_fam_core(request, execute=True, fingerprint=request.approval_fingerprint), actual)
    if request.mode is SearchMode.COUNT:
        return LiveText7aResult(
            document_name=request.document_name,
            command_alias="FAM",
            matched_handles=plan.matched_handles,
            postcondition_verified=True,
        )
    if request.mark_shape not in {MarkShape.CIRCLE, MarkShape.BLOCK}:
        raise ValueError("unsupported FAM live marker shape")
    doc = adapter.connect()
    created: list[Any] = []
    primary_created: list[Any] = []
    doc.StartUndoMark()
    try:
        for marker in plan.markers:
            owner = adapter.owner(marker.source_handle)
            if marker.shape is MarkShape.CIRCLE:
                entity = owner.AddCircle(adapter.vector(marker.center), marker.radius)
            else:
                entity = owner.InsertBlock(adapter.vector(marker.center), marker.block_name, 1.0, 1.0, 1.0, 0.0)
            entity.Layer = marker.layer
            created.append(entity)
            primary_created.append(entity)
            if marker.mark_insertion_point:
                point = owner.AddPoint(adapter.vector(marker.center))
                point.Layer = marker.layer
                created.append(point)
    finally:
        doc.EndUndoMark()
    after = adapter.objects()
    handles = tuple(str(entity.Handle) for entity in created)
    verified = all(handle.casefold() in after for handle in handles)
    for entity, marker in zip(primary_created, plan.markers, strict=True):
        verified = verified and str(entity.Layer) == marker.layer
        if marker.shape is MarkShape.CIRCLE:
            verified = verified and abs(float(entity.Radius) - float(marker.radius)) <= 1e-9
        else:
            try:
                name = str(entity.EffectiveName)
            except Exception:
                name = str(entity.Name)
            verified = verified and name.casefold() == str(marker.block_name).casefold()
    if not verified:
        raise RuntimeError("FAM postcondition failed")
    return LiveText7aResult(
        document_name=str(doc.Name),
        command_alias="FAM",
        matched_handles=plan.matched_handles,
        created_handles=handles,
        postcondition_verified=True,
    )


def _ftt_core(request: LiveFttPreviewRequest, *, execute: bool, fingerprint: str | None = None) -> FieldToTextRequest:
    return FieldToTextRequest(
        document_id=request.document_name,
        target_handles=tuple(item.handle for item in request.resolutions),
        unresolved_policy=request.unresolved_policy,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_ftt(request: LiveFttPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveText7aAdapter(request.document_name)
    fields = adapter.fields(request.resolutions)
    plan = plan_field_to_text(_ftt_core(request, execute=False), fields)
    payload = {**request.model_dump(mode="json"), "expected_fields": _models(fields)}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_ftt(request: LiveFttExecuteRequest) -> LiveText7aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact FTT request")
    adapter = ZWCADLiveText7aAdapter(request.document_name)
    actual = adapter.fields(request.resolutions)
    _ensure_same(actual, request.expected_fields, "FTT")
    plan = plan_field_to_text(_ftt_core(request, execute=True, fingerprint=request.approval_fingerprint), actual)
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            adapter.entity(change.handle).TextString = change.replacement_text
    finally:
        doc.EndUndoMark()
    verified = all(str(adapter.entity(c.handle).TextString) == c.replacement_text for c in plan.changes)
    if not verified:
        raise RuntimeError("FTT postcondition failed")
    return LiveText7aResult(
        document_name=str(doc.Name),
        command_alias="FTT",
        changed_handles=tuple(c.handle for c in plan.changes),
        postcondition_verified=True,
    )


def _t2m_core(request: LiveT2mPreviewRequest, *, execute: bool, fingerprint: str | None = None) -> TextToMTextRequest:
    return TextToMTextRequest(
        document_id=request.document_name,
        target_handles=request.target_handles,
        source_disposition=request.source_disposition,
        preserve_visual_width=request.preserve_visual_width,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_t2m(request: LiveT2mPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveText7aAdapter(request.document_name)
    entities = adapter.snapshots(request.target_handles)
    plan = plan_text_to_mtext(_t2m_core(request, execute=False), entities)
    payload = {**request.model_dump(mode="json"), "expected_entities": _models(entities)}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_t2m(request: LiveT2mExecuteRequest) -> LiveText7aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact T2M request")
    adapter = ZWCADLiveText7aAdapter(request.document_name)
    actual = adapter.snapshots(request.target_handles)
    _ensure_same(actual, request.expected_entities, "T2M")
    plan = plan_text_to_mtext(_t2m_core(request, execute=True, fingerprint=request.approval_fingerprint), actual)
    doc = adapter.connect()
    created: list[Any] = []
    doc.StartUndoMark()
    try:
        for conversion in plan.conversions:
            source = adapter.entity(conversion.source_handle)
            minimum, maximum = adapter.bbox(source)
            visual_width = max(maximum.x - minimum.x, conversion.text_height)
            width = (
                visual_width
                if conversion.preserve_visual_width
                else max(conversion.text_height, conversion.text_height * max(len(conversion.text), 1) * 2)
            )
            entity = adapter.owner(conversion.source_handle).AddMText(
                adapter.vector(conversion.insertion_point), width, conversion.text
            )
            entity.Layer = conversion.layer
            entity.StyleName = conversion.text_style
            entity.TextHeight = conversion.text_height
            entity.Rotation = radians(conversion.rotation_degrees)
            created.append(entity)
            if conversion.erase_source:
                source.Delete()
    finally:
        doc.EndUndoMark()
    after = adapter.objects()
    handles = tuple(str(entity.Handle) for entity in created)
    erased = tuple(c.source_handle for c in plan.conversions if c.erase_source)
    verified = all(h.casefold() in after for h in handles) and all(h.casefold() not in after for h in erased)
    verified = verified and all(
        str(entity.TextString) == conversion.text for entity, conversion in zip(created, plan.conversions, strict=True)
    )
    verified = verified and all(
        str(entity.Layer) == conversion.layer
        and str(entity.StyleName) == conversion.text_style
        and abs(float(entity.TextHeight) - conversion.text_height) <= 1e-9
        and abs(float(entity.Rotation) - radians(conversion.rotation_degrees)) <= 1e-9
        for entity, conversion in zip(created, plan.conversions, strict=True)
    )
    if not verified:
        raise RuntimeError("T2M postcondition failed")
    return LiveText7aResult(
        document_name=str(doc.Name),
        command_alias="T2M",
        created_handles=handles,
        erased_handles=erased,
        postcondition_verified=True,
    )


def _tec_core(request: LiveTecPreviewRequest) -> PartialTextCopyRequest:
    return PartialTextCopyRequest(
        document_id=request.document_name,
        target_handles=request.target_handles,
        mode=request.mode,
        start=request.start,
        end=request.end,
        pattern=request.pattern,
        group=request.group,
    )


def preview_live_tec(request: LiveTecPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveText7aAdapter(request.document_name)
    entities = adapter.snapshots(request.target_handles)
    plan = plan_partial_text_copy(_tec_core(request), entities)
    payload = {**request.model_dump(mode="json"), "expected_entities": _models(entities)}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_tec(request: LiveTecExecuteRequest) -> LiveText7aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact TEC request")
    adapter = ZWCADLiveText7aAdapter(request.document_name)
    actual = adapter.snapshots(request.target_handles)
    _ensure_same(actual, request.expected_entities, "TEC")
    plan = plan_partial_text_copy(_tec_core(request), actual)
    return LiveText7aResult(
        document_name=request.document_name,
        command_alias="TEC",
        matched_handles=tuple(item.source_handle for item in plan.extracted),
        extracted_values=tuple(item.value for item in plan.extracted),
        postcondition_verified=True,
    )


_TEXT_ALIGN = {
    TextJustification.LEFT: 0,
    TextJustification.CENTER: 1,
    TextJustification.RIGHT: 2,
    TextJustification.MIDDLE: 4,
    TextJustification.TOP_LEFT: 6,
    TextJustification.TOP_CENTER: 7,
    TextJustification.TOP_RIGHT: 8,
    TextJustification.BOTTOM_LEFT: 12,
    TextJustification.BOTTOM_CENTER: 13,
    TextJustification.BOTTOM_RIGHT: 14,
}
_MTEXT_ALIGN = {
    TextJustification.TOP_LEFT: 1,
    TextJustification.TOP_CENTER: 2,
    TextJustification.TOP_RIGHT: 3,
    TextJustification.MIDDLE: 5,
    TextJustification.BOTTOM_LEFT: 7,
    TextJustification.BOTTOM_CENTER: 8,
    TextJustification.BOTTOM_RIGHT: 9,
}


def _tj_core(request: LiveTjPreviewRequest, *, execute: bool, fingerprint: str | None = None) -> JustificationRequest:
    return JustificationRequest(
        document_id=request.document_name,
        target_handles=request.target_handles,
        justification=request.justification,
        preserve_visual_position=request.preserve_visual_position,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_tj(request: LiveTjPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveText7aAdapter(request.document_name)
    entities = adapter.snapshots(request.target_handles)
    for entity in entities:
        mapping = _MTEXT_ALIGN if entity.kind is TextEntityKind.MTEXT else _TEXT_ALIGN
        if request.justification not in mapping:
            raise ValueError(f"TJ justification is ambiguous for {entity.kind}: {request.justification}")
    plan = plan_justification(_tj_core(request, execute=False), entities)
    payload = {**request.model_dump(mode="json"), "expected_entities": _models(entities)}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_tj(request: LiveTjExecuteRequest) -> LiveText7aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact TJ request")
    adapter = ZWCADLiveText7aAdapter(request.document_name)
    actual = adapter.snapshots(request.target_handles)
    _ensure_same(actual, request.expected_entities, "TJ")
    plan = plan_justification(_tj_core(request, execute=True, fingerprint=request.approval_fingerprint), actual)
    by_handle = {item.handle.casefold(): item for item in actual}
    doc = adapter.connect()
    visual_centers: dict[str, Point3D] = {}
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            entity = adapter.entity(change.handle)
            before_min, before_max = adapter.bbox(entity)
            visual_centers[change.handle.casefold()] = Point3D(
                x=(before_min.x + before_max.x) / 2,
                y=(before_min.y + before_max.y) / 2,
                z=(before_min.z + before_max.z) / 2,
            )
            kind = by_handle[change.handle.casefold()].kind
            if kind is TextEntityKind.MTEXT:
                entity.AttachmentPoint = _MTEXT_ALIGN[change.justification]
            else:
                entity.Alignment = _TEXT_ALIGN[change.justification]
            if change.preserve_visual_position:
                after_min, after_max = adapter.bbox(entity)
                delta = Point3D(
                    x=(before_min.x + before_max.x - after_min.x - after_max.x) / 2,
                    y=(before_min.y + before_max.y - after_min.y - after_max.y) / 2,
                    z=(before_min.z + before_max.z - after_min.z - after_max.z) / 2,
                )
                entity.Move(adapter.vector(Point3D(x=0, y=0, z=0)), adapter.vector(delta))
    finally:
        doc.EndUndoMark()
    verified = all(
        int(
            adapter.entity(c.handle).AttachmentPoint
            if by_handle[c.handle.casefold()].kind is TextEntityKind.MTEXT
            else adapter.entity(c.handle).Alignment
        )
        == (_MTEXT_ALIGN if by_handle[c.handle.casefold()].kind is TextEntityKind.MTEXT else _TEXT_ALIGN)[
            c.justification
        ]
        for c in plan.changes
    )
    for change in plan.changes:
        if not change.preserve_visual_position:
            continue
        minimum, maximum = adapter.bbox(adapter.entity(change.handle))
        before_center = visual_centers[change.handle.casefold()]
        after_center = Point3D(
            x=(minimum.x + maximum.x) / 2,
            y=(minimum.y + maximum.y) / 2,
            z=(minimum.z + maximum.z) / 2,
        )
        verified = verified and all(
            abs(before - after) <= 1e-7
            for before, after in zip(
                before_center.model_dump().values(),
                after_center.model_dump().values(),
                strict=True,
            )
        )
    if not verified:
        raise RuntimeError("TJ postcondition failed")
    return LiveText7aResult(
        document_name=str(doc.Name),
        command_alias="TJ",
        changed_handles=tuple(c.handle for c in plan.changes),
        postcondition_verified=True,
    )


def _tsa_core(request: LiveTsaPreviewRequest, *, execute: bool, fingerprint: str | None = None) -> TextStyleRequest:
    return TextStyleRequest(
        document_id=request.document_name,
        target_style=request.target_style,
        scope=StyleScope.DOCUMENT,
        spaces=request.spaces,
        allowed_kinds=request.allowed_kinds,
        dry_run=not execute,
        approval=_approval(execute, fingerprint),
    )


def preview_live_tsa(request: LiveTsaPreviewRequest) -> dict[str, Any]:
    adapter = ZWCADLiveText7aAdapter(request.document_name)
    try:
        adapter.connect().TextStyles.Item(request.target_style)
    except Exception as exc:
        raise ValueError(f"target text style does not exist: {request.target_style}") from exc
    entities = adapter.snapshots()
    plan = plan_text_style(_tsa_core(request, execute=False), entities, alias="TSA")
    selected = tuple(
        item for item in entities if any(c.handle.casefold() == item.handle.casefold() for c in plan.changes)
    )
    payload = {**request.model_dump(mode="json"), "expected_entities": _models(selected)}
    return {**payload, "plan": plan.model_dump(mode="json"), "approval_fingerprint": _hash(payload)}


def execute_live_tsa(request: LiveTsaExecuteRequest) -> LiveText7aResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact TSA request")
    adapter = ZWCADLiveText7aAdapter(request.document_name)
    current_all = adapter.snapshots()
    plan = plan_text_style(
        _tsa_core(request, execute=True, fingerprint=request.approval_fingerprint), current_all, alias="TSA"
    )
    selected = tuple(
        item for item in current_all if any(c.handle.casefold() == item.handle.casefold() for c in plan.changes)
    )
    _ensure_same(selected, request.expected_entities, "TSA")
    doc = adapter.connect()
    doc.StartUndoMark()
    try:
        for change in plan.changes:
            adapter.entity(change.handle).StyleName = change.replacement_style
    finally:
        doc.EndUndoMark()
    if not all(str(adapter.entity(c.handle).StyleName) == c.replacement_style for c in plan.changes):
        raise RuntimeError("TSA postcondition failed")
    return LiveText7aResult(
        document_name=str(doc.Name),
        command_alias="TSA",
        changed_handles=tuple(c.handle for c in plan.changes),
        postcondition_verified=True,
    )


def register_live_text_batch7a_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview live xiCAD Batch 7A text operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute = ToolAnnotations(
        title="Execute live xiCAD Batch 7A text operation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    read_execute = ToolAnnotations(
        title="Execute CAD-read xiCAD TEC extraction",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_fam", preview_live_fam, preview),
        ("xicad_execute_live_fam", execute_live_fam, execute),
        ("xicad_preview_live_ftt", preview_live_ftt, preview),
        ("xicad_execute_live_ftt", execute_live_ftt, execute),
        ("xicad_preview_live_t2m", preview_live_t2m, preview),
        ("xicad_execute_live_t2m", execute_live_t2m, execute),
        ("xicad_preview_live_tec", preview_live_tec, preview),
        ("xicad_execute_live_tec", execute_live_tec, read_execute),
        ("xicad_preview_live_tj", preview_live_tj, preview),
        ("xicad_execute_live_tj", execute_live_tj, execute),
        ("xicad_preview_live_tsa", preview_live_tsa, preview),
        ("xicad_execute_live_tsa", execute_live_tsa, execute),
    )
    for name, function, tool_annotations in registrations:
        mcp.tool(name=name, annotations=tool_annotations)(function)
