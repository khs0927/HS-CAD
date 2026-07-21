from __future__ import annotations

import re
from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch5 import DrawingSpace, TextChange, TextEntityKind, TextEntitySnapshot


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval")


def _selected(handles: Sequence[str], entities: Sequence[TextEntitySnapshot]) -> tuple[TextEntitySnapshot, ...]:
    result = _looked_up(handles, entities)
    for entity in result:
        if entity.is_xref:
            raise ValueError(f"xref text cannot be mutated: {entity.handle}")
        if entity.locked_layer:
            raise ValueError(f"locked-layer text cannot be mutated: {entity.handle}")
    return result


def _looked_up(handles: Sequence[str], entities: Sequence[TextEntitySnapshot]) -> tuple[TextEntitySnapshot, ...]:
    folded = [handle.casefold() for handle in handles]
    if len(folded) != len(set(folded)):
        raise ValueError("target_handles must be unique")
    by_handle = {entity.handle.casefold(): entity for entity in entities}
    if len(by_handle) != len(entities):
        raise ValueError("entity handles must be unique")
    result = []
    for handle in handles:
        entity = by_handle.get(handle.casefold())
        if entity is None:
            raise ValueError(f"text entity not found: {handle}")
        result.append(entity)
    return tuple(result)


class Batch7Plan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class SearchMode(StrEnum):
    MARK = "mark"
    COUNT = "count"


class MarkShape(StrEnum):
    BOX = "box"
    CIRCLE = "circle"
    LINE = "line"
    BLOCK = "block"


class FindMarkRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
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
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_mode(self) -> FindMarkRequest:
        if self.target_handles is not None and len(self.target_handles) != len(set(h.casefold() for h in self.target_handles)):
            raise ValueError("target_handles must be unique")
        if self.mode is SearchMode.MARK:
            if self.mark_shape is None or not self.mark_layer:
                raise ValueError("FAM mark mode requires mark_shape and mark_layer")
            if self.mark_shape is MarkShape.CIRCLE and self.circle_radius is None:
                raise ValueError("FAM circle mark requires circle_radius")
            if self.mark_shape is MarkShape.BLOCK and not self.block_name:
                raise ValueError("FAM block mark requires block_name")
            _approval(self.dry_run, self.approval, "FAM")
        return self


class TextMarker(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    shape: MarkShape
    layer: str
    center: Point3D
    radius: float | None = None
    block_name: str | None = None
    mark_insertion_point: bool


class FindMarkPlan(Batch7Plan):
    command_alias: str = "FAM"
    legacy_symbol: str = "xiFindAndMark"
    matched_handles: tuple[str, ...]
    match_count: int
    markers: tuple[TextMarker, ...]


def plan_find_and_mark(request: FindMarkRequest, entities: Sequence[TextEntitySnapshot]) -> FindMarkPlan:
    candidates = entities if request.target_handles is None else _looked_up(request.target_handles, entities)
    def normalize(value: str) -> str:
        if request.ignore_spaces:
            value = re.sub(r"\s+", "", value)
        return value if request.case_sensitive else value.casefold()
    query = normalize(request.query)
    matches = []
    for entity in candidates:
        if entity.kind not in request.allowed_kinds or entity.is_xref:
            continue
        if request.exclude_locked_layers and entity.locked_layer:
            continue
        text = normalize(entity.text)
        if (text == query) if request.whole_string else (query in text):
            matches.append(entity)
    markers = ()
    if request.mode is SearchMode.MARK:
        markers = tuple(TextMarker(source_handle=e.handle, shape=request.mark_shape, layer=request.mark_layer,
                                   center=e.insertion_point, radius=request.circle_radius,
                                   block_name=request.block_name, mark_insertion_point=request.mark_insertion_point)
                        for e in matches)
    return FindMarkPlan(document_id=request.document_id, matched_handles=tuple(e.handle for e in matches),
                        match_count=len(matches), markers=markers, dry_run=request.dry_run)


class UnresolvedFieldPolicy(StrEnum):
    ERROR = "error"
    KEEP_FIELD = "keep_field"
    USE_LITERAL_FALLBACK = "use_literal_fallback"


class FieldTextSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    field_expression: str = Field(min_length=1)
    evaluated_text: str | None = None
    literal_fallback: str | None = None
    locked_layer: bool = False
    is_xref: bool = False


class FieldToTextRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    unresolved_policy: UnresolvedFieldPolicy
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> FieldToTextRequest:
        if len(self.target_handles) != len(set(handle.casefold() for handle in self.target_handles)):
            raise ValueError("FTT target_handles must be unique")
        _approval(self.dry_run, self.approval, "FTT")
        return self


class TextChangesPlan(Batch7Plan):
    changes: tuple[TextChange, ...]


def plan_field_to_text(request: FieldToTextRequest, fields: Sequence[FieldTextSnapshot]) -> TextChangesPlan:
    by_handle = {f.handle.casefold(): f for f in fields}
    if len(by_handle) != len(fields):
        raise ValueError("field handles must be unique")
    changes = []
    for handle in request.target_handles:
        field = by_handle.get(handle.casefold())
        if field is None:
            raise ValueError(f"field not found: {handle}")
        if field.is_xref or field.locked_layer:
            raise ValueError(f"field cannot be mutated: {handle}")
        replacement = field.evaluated_text
        if replacement is None:
            if request.unresolved_policy is UnresolvedFieldPolicy.ERROR:
                raise ValueError(f"unresolved field: {handle}")
            if request.unresolved_policy is UnresolvedFieldPolicy.KEEP_FIELD:
                continue
            replacement = field.literal_fallback
            if replacement is None:
                raise ValueError(f"literal fallback missing: {handle}")
        changes.append(TextChange(handle=field.handle, expected_text=field.field_expression, replacement_text=replacement))
    return TextChangesPlan(command_alias="FTT", legacy_symbol="xiField2Text", document_id=request.document_id,
                           changes=tuple(changes), dry_run=request.dry_run)


class SourceDisposition(StrEnum):
    REPLACE = "replace"
    PRESERVE = "preserve"


class TextToMTextRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    source_disposition: SourceDisposition
    preserve_visual_width: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TextToMTextRequest:
        _approval(self.dry_run, self.approval, "T2M")
        return self


class MTextConversion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    text: str
    insertion_point: Point3D
    layer: str
    text_style: str
    text_height: float
    rotation_degrees: float
    preserve_visual_width: bool
    erase_source: bool


class TextToMTextPlan(Batch7Plan):
    command_alias: str = "T2M"
    legacy_symbol: str = "xiT2MT"
    conversions: tuple[MTextConversion, ...]


def plan_text_to_mtext(request: TextToMTextRequest, entities: Sequence[TextEntitySnapshot]) -> TextToMTextPlan:
    selected = _selected(request.target_handles, entities)
    for entity in selected:
        if entity.kind is not TextEntityKind.TEXT:
            raise ValueError(f"T2M requires single-line text: {entity.handle}")
    return TextToMTextPlan(document_id=request.document_id, conversions=tuple(MTextConversion(
        source_handle=e.handle, text=e.text, insertion_point=e.insertion_point, layer=e.layer,
        text_style=e.text_style, text_height=e.text_height, rotation_degrees=e.rotation_degrees,
        preserve_visual_width=request.preserve_visual_width,
        erase_source=request.source_disposition is SourceDisposition.REPLACE) for e in selected), dry_run=request.dry_run)


class SubstringMode(StrEnum):
    SLICE = "slice"
    REGEX_GROUP = "regex_group"


class PartialTextCopyRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    mode: SubstringMode
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    pattern: str | None = None
    group: int = Field(default=0, ge=0)
    dry_run: bool = True

    @model_validator(mode="after")
    def validate_mode(self) -> PartialTextCopyRequest:
        if self.mode is SubstringMode.SLICE and self.start is None:
            raise ValueError("TEC slice mode requires start")
        if self.mode is SubstringMode.SLICE and self.end is not None and self.end < self.start:
            raise ValueError("TEC end must not precede start")
        if self.mode is SubstringMode.REGEX_GROUP:
            if not self.pattern:
                raise ValueError("TEC regex_group mode requires pattern")
            re.compile(self.pattern)
        return self


class ExtractedText(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    value: str


class PartialTextCopyPlan(Batch7Plan):
    command_alias: str = "TEC"
    legacy_symbol: str = "xiTextEntryCopy"
    extracted: tuple[ExtractedText, ...]


def plan_partial_text_copy(request: PartialTextCopyRequest, entities: Sequence[TextEntitySnapshot]) -> PartialTextCopyPlan:
    selected = _looked_up(request.target_handles, entities)
    result = []
    for entity in selected:
        if request.mode is SubstringMode.SLICE:
            value = entity.text[request.start:request.end]
        else:
            match = re.search(request.pattern, entity.text)
            if match is None or request.group > (match.lastindex or 0):
                raise ValueError(f"TEC pattern/group did not match: {entity.handle}")
            value = match.group(request.group)
        result.append(ExtractedText(source_handle=entity.handle, value=value))
    return PartialTextCopyPlan(document_id=request.document_id, extracted=tuple(result), dry_run=request.dry_run)


class TextJustification(StrEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    MIDDLE = "middle"
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


class JustificationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    justification: TextJustification
    preserve_visual_position: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> JustificationRequest:
        _approval(self.dry_run, self.approval, "TJ")
        return self


class JustificationChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    justification: TextJustification
    preserve_visual_position: bool


class JustificationPlan(Batch7Plan):
    command_alias: str = "TJ"
    legacy_symbol: str = "xiTJus"
    changes: tuple[JustificationChange, ...]


def plan_justification(request: JustificationRequest, entities: Sequence[TextEntitySnapshot]) -> JustificationPlan:
    selected = _selected(request.target_handles, entities)
    return JustificationPlan(document_id=request.document_id,
        changes=tuple(JustificationChange(handle=e.handle, justification=request.justification,
                                          preserve_visual_position=request.preserve_visual_position) for e in selected),
        dry_run=request.dry_run)


class StyleScope(StrEnum):
    SELECTED = "selected"
    DOCUMENT = "document"


class TextStyleRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_style: str = Field(min_length=1)
    scope: StyleScope
    target_handles: tuple[str, ...] = ()
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)
    allowed_kinds: tuple[TextEntityKind, ...] = tuple(TextEntityKind)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_scope(self) -> TextStyleRequest:
        if self.scope is StyleScope.SELECTED and not self.target_handles:
            raise ValueError("selected style scope requires target_handles")
        if self.scope is StyleScope.DOCUMENT and self.target_handles:
            raise ValueError("document style scope does not accept target_handles")
        _approval(self.dry_run, self.approval, "TSA/TST")
        return self


class StyleChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_style: str
    replacement_style: str


class TextStylePlan(Batch7Plan):
    changes: tuple[StyleChange, ...]


def plan_text_style(request: TextStyleRequest, entities: Sequence[TextEntitySnapshot], *, alias: str) -> TextStylePlan:
    if alias not in {"TSA", "TST"}:
        raise ValueError("alias must be TSA or TST")
    if alias == "TSA" and request.scope is not StyleScope.DOCUMENT:
        raise ValueError("TSA requires document scope")
    if alias == "TST" and request.scope is not StyleScope.SELECTED:
        raise ValueError("TST requires selected scope")
    selected = (_selected(request.target_handles, entities) if request.scope is StyleScope.SELECTED else
                tuple(e for e in entities if e.space in request.spaces and e.kind in request.allowed_kinds and not e.is_xref))
    if any(e.locked_layer for e in selected):
        raise ValueError("style target is on a locked layer")
    return TextStylePlan(command_alias=alias, legacy_symbol="xiTextStyleALL" if alias == "TSA" else "xiTsty",
                         document_id=request.document_id,
                         changes=tuple(StyleChange(handle=e.handle, expected_style=e.text_style,
                                                   replacement_style=request.target_style) for e in selected),
                         dry_run=request.dry_run)


class SequentialEdit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    expected_text: str
    replacement_text: str


class SequentialEditRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    edits: tuple[SequentialEdit, ...] = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> SequentialEditRequest:
        if len({e.handle.casefold() for e in self.edits}) != len(self.edits):
            raise ValueError("TSE edit handles must be unique")
        _approval(self.dry_run, self.approval, "TSE")
        return self


def plan_sequential_edit(request: SequentialEditRequest, entities: Sequence[TextEntitySnapshot]) -> TextChangesPlan:
    selected = _selected(tuple(e.handle for e in request.edits), entities)
    by_handle = {e.handle.casefold(): e for e in selected}
    changes = []
    for edit in request.edits:
        entity = by_handle[edit.handle.casefold()]
        if entity.text != edit.expected_text:
            raise ValueError(f"TSE expected text mismatch: {edit.handle}")
        changes.append(TextChange(handle=entity.handle, expected_text=entity.text, replacement_text=edit.replacement_text))
    return TextChangesPlan(command_alias="TSE", legacy_symbol="xiTextSE", document_id=request.document_id,
                           changes=tuple(changes), dry_run=request.dry_run)


class StackDirection(StrEnum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class StackAnchor(StrEnum):
    FIRST = "first"
    EXPLICIT = "explicit"


class TextStackRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    direction: StackDirection
    gap: float = Field(ge=0)
    anchor: StackAnchor
    anchor_point: Point3D | None = None
    order: tuple[str, ...] | None = None
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TextStackRequest:
        if self.anchor is StackAnchor.EXPLICIT and self.anchor_point is None:
            raise ValueError("TSO explicit anchor requires anchor_point")
        if self.order is not None:
            ordered = [handle.casefold() for handle in self.order]
            targets = [handle.casefold() for handle in self.target_handles]
            if len(ordered) != len(set(ordered)) or len(ordered) != len(targets) or set(ordered) != set(targets):
                raise ValueError("TSO order must contain every target exactly once")
        _approval(self.dry_run, self.approval, "TSO")
        return self


class MoveSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    from_point: Point3D
    to_point: Point3D


class TextStackPlan(Batch7Plan):
    command_alias: str = "TSO"
    legacy_symbol: str = "xiTextStack"
    moves: tuple[MoveSpec, ...]


def plan_text_stack(request: TextStackRequest, entities: Sequence[TextEntitySnapshot]) -> TextStackPlan:
    selected = _selected(request.target_handles, entities)
    by_handle = {e.handle.casefold(): e for e in selected}
    ordered = selected if request.order is None else tuple(by_handle[h.casefold()] for h in request.order)
    anchor = request.anchor_point if request.anchor is StackAnchor.EXPLICIT else ordered[0].insertion_point
    moves = []
    for index, entity in enumerate(ordered):
        step = index * request.gap
        point = Point3D(x=anchor.x + (step if request.direction is StackDirection.HORIZONTAL else 0),
                        y=anchor.y - (step if request.direction is StackDirection.VERTICAL else 0), z=anchor.z)
        moves.append(MoveSpec(handle=entity.handle, from_point=entity.insertion_point, to_point=point))
    return TextStackPlan(document_id=request.document_id, moves=tuple(moves), dry_run=request.dry_run)


class SplitMode(StrEnum):
    DELIMITER = "delimiter"
    FIXED_INDEX = "fixed_index"
    REGEX = "regex"


class TextSplitRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    mode: SplitMode
    delimiter: str | None = None
    indices: tuple[int, ...] = ()
    pattern: str | None = None
    keep_empty: bool = False
    source_disposition: SourceDisposition
    offset: Point3D
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_mode(self) -> TextSplitRequest:
        if self.mode is SplitMode.DELIMITER and not self.delimiter:
            raise ValueError("TSP delimiter mode requires delimiter")
        if self.mode is SplitMode.FIXED_INDEX and (not self.indices or tuple(sorted(set(self.indices))) != self.indices):
            raise ValueError("TSP fixed indices must be unique and ascending")
        if self.mode is SplitMode.REGEX:
            if not self.pattern:
                raise ValueError("TSP regex mode requires pattern")
            re.compile(self.pattern)
        _approval(self.dry_run, self.approval, "TSP")
        return self


class SplitPiece(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    ordinal: int
    text: str
    insertion_point: Point3D
    layer: str
    text_style: str
    text_height: float


class TextSplitPlan(Batch7Plan):
    command_alias: str = "TSP"
    legacy_symbol: str = "xiTextSeparate"
    pieces: tuple[SplitPiece, ...]
    erase_source_handles: tuple[str, ...]


def plan_text_split(request: TextSplitRequest, entities: Sequence[TextEntitySnapshot]) -> TextSplitPlan:
    selected = _selected(request.target_handles, entities)
    pieces = []
    for entity in selected:
        if request.mode is SplitMode.DELIMITER:
            values = entity.text.split(request.delimiter)
        elif request.mode is SplitMode.REGEX:
            values = re.split(request.pattern, entity.text)
        else:
            cuts = (0, *request.indices, len(entity.text))
            if cuts[-2] > len(entity.text):
                raise ValueError(f"TSP split index exceeds text length: {entity.handle}")
            values = [entity.text[a:b] for a, b in zip(cuts, cuts[1:], strict=True)]
        if not request.keep_empty:
            values = [value for value in values if value]
        for index, value in enumerate(values):
            pieces.append(SplitPiece(source_handle=entity.handle, ordinal=index, text=value,
                insertion_point=Point3D(x=entity.insertion_point.x + request.offset.x * index,
                                        y=entity.insertion_point.y + request.offset.y * index,
                                        z=entity.insertion_point.z + request.offset.z * index),
                layer=entity.layer, text_style=entity.text_style, text_height=entity.text_height))
    erased = request.target_handles if request.source_disposition is SourceDisposition.REPLACE else ()
    return TextSplitPlan(document_id=request.document_id, pieces=tuple(pieces), erase_source_handles=erased,
                         dry_run=request.dry_run)


class TextSwapRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    first_handle: str = Field(min_length=1)
    second_handle: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TextSwapRequest:
        if self.first_handle.casefold() == self.second_handle.casefold():
            raise ValueError("TSW requires two distinct handles")
        _approval(self.dry_run, self.approval, "TSW")
        return self


def plan_text_swap(request: TextSwapRequest, entities: Sequence[TextEntitySnapshot]) -> TextChangesPlan:
    first, second = _selected((request.first_handle, request.second_handle), entities)
    return TextChangesPlan(command_alias="TSW", legacy_symbol="xiTextSW", document_id=request.document_id,
        changes=(TextChange(handle=first.handle, expected_text=first.text, replacement_text=second.text),
                 TextChange(handle=second.handle, expected_text=second.text, replacement_text=first.text)),
        dry_run=request.dry_run)


class TextWidthRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    width_factor: float = Field(gt=0, le=100)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TextWidthRequest:
        _approval(self.dry_run, self.approval, "TW")
        return self


class WidthChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    width_factor: float


class TextWidthPlan(Batch7Plan):
    command_alias: str = "TW"
    legacy_symbol: str = "xiTWid"
    changes: tuple[WidthChange, ...]


def plan_text_width(request: TextWidthRequest, entities: Sequence[TextEntitySnapshot]) -> TextWidthPlan:
    selected = _selected(request.target_handles, entities)
    return TextWidthPlan(document_id=request.document_id,
                         changes=tuple(WidthChange(handle=e.handle, width_factor=request.width_factor) for e in selected),
                         dry_run=request.dry_run)


def register_headless_core_batch7_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(title="xiCAD Headless Core Batch 7 Planner", readOnlyHint=True,
                                destructiveHint=False, idempotentHint=True, openWorldHint=False)

    @mcp.tool(name="xicad_plan_fam", annotations=read_only)
    def mcp_plan_fam(request: FindMarkRequest, entities: tuple[TextEntitySnapshot, ...]) -> FindMarkPlan:
        return plan_find_and_mark(request, entities)

    @mcp.tool(name="xicad_plan_ftt", annotations=read_only)
    def mcp_plan_ftt(request: FieldToTextRequest, fields: tuple[FieldTextSnapshot, ...]) -> TextChangesPlan:
        return plan_field_to_text(request, fields)

    @mcp.tool(name="xicad_plan_t2m", annotations=read_only)
    def mcp_plan_t2m(request: TextToMTextRequest, entities: tuple[TextEntitySnapshot, ...]) -> TextToMTextPlan:
        return plan_text_to_mtext(request, entities)

    @mcp.tool(name="xicad_plan_tec", annotations=read_only)
    def mcp_plan_tec(request: PartialTextCopyRequest, entities: tuple[TextEntitySnapshot, ...]) -> PartialTextCopyPlan:
        return plan_partial_text_copy(request, entities)

    @mcp.tool(name="xicad_plan_tj", annotations=read_only)
    def mcp_plan_tj(request: JustificationRequest, entities: tuple[TextEntitySnapshot, ...]) -> JustificationPlan:
        return plan_justification(request, entities)

    @mcp.tool(name="xicad_plan_tsa", annotations=read_only)
    def mcp_plan_tsa(request: TextStyleRequest, entities: tuple[TextEntitySnapshot, ...]) -> TextStylePlan:
        return plan_text_style(request, entities, alias="TSA")

    @mcp.tool(name="xicad_plan_tse", annotations=read_only)
    def mcp_plan_tse(request: SequentialEditRequest, entities: tuple[TextEntitySnapshot, ...]) -> TextChangesPlan:
        return plan_sequential_edit(request, entities)

    @mcp.tool(name="xicad_plan_tso", annotations=read_only)
    def mcp_plan_tso(request: TextStackRequest, entities: tuple[TextEntitySnapshot, ...]) -> TextStackPlan:
        return plan_text_stack(request, entities)

    @mcp.tool(name="xicad_plan_tsp", annotations=read_only)
    def mcp_plan_tsp(request: TextSplitRequest, entities: tuple[TextEntitySnapshot, ...]) -> TextSplitPlan:
        return plan_text_split(request, entities)

    @mcp.tool(name="xicad_plan_tst", annotations=read_only)
    def mcp_plan_tst(request: TextStyleRequest, entities: tuple[TextEntitySnapshot, ...]) -> TextStylePlan:
        return plan_text_style(request, entities, alias="TST")

    @mcp.tool(name="xicad_plan_tsw", annotations=read_only)
    def mcp_plan_tsw(request: TextSwapRequest, entities: tuple[TextEntitySnapshot, ...]) -> TextChangesPlan:
        return plan_text_swap(request, entities)

    @mcp.tool(name="xicad_plan_tw", annotations=read_only)
    def mcp_plan_tw(request: TextWidthRequest, entities: tuple[TextEntitySnapshot, ...]) -> TextWidthPlan:
        return plan_text_width(request, entities)
