from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum
from math import isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch5 import DrawingSpace, TextChange, TextEntityKind, TextEntitySnapshot, TextWriteSpec


def _approval(dry_run: bool, approval: Approval, alias: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{alias} execution requires explicit approval")


def _unique(values: Sequence[str], name: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{name} must be unique")


def _selected(handles: Sequence[str], entities: Sequence[TextEntitySnapshot]) -> tuple[TextEntitySnapshot, ...]:
    _unique(handles, "target_handles")
    by_handle = {entity.handle.casefold(): entity for entity in entities}
    if len(by_handle) != len(entities):
        raise ValueError("entity handles must be unique")
    result = []
    for handle in handles:
        entity = by_handle.get(handle.casefold())
        if entity is None:
            raise ValueError(f"text entity not found: {handle}")
        if entity.is_xref or entity.locked_layer:
            raise ValueError(f"text entity cannot be mutated: {handle}")
        result.append(entity)
    return tuple(result)


class Batch8Plan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


# A2M -- recovered DCL distinguishes attribute-to-text and block-attributes-to-mtext.
class AttributeConversionMode(StrEnum):
    ATTRIBUTE_TO_TEXT = "attribute_to_text"
    BLOCK_ATTRIBUTES_TO_MTEXT = "block_attributes_to_mtext"


class SourceDisposition(StrEnum):
    PRESERVE = "preserve"
    REPLACE = "replace"


class AttributeSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    owner_block_handle: str = Field(min_length=1)
    tag: str = Field(min_length=1)
    value: str
    insertion_point: Point3D
    layer: str = Field(min_length=1)
    text_style: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    rotation_degrees: float = 0
    locked_layer: bool = False
    is_xref: bool = False


class AttributeToTextRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    mode: AttributeConversionMode
    include_tag: bool
    tag_separator: str = ": "
    block_separator: str = "\\P"
    source_disposition: SourceDisposition
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> AttributeToTextRequest:
        _unique(self.target_handles, "target_handles")
        _approval(self.dry_run, self.approval, "A2M")
        return self


class AttributeTextConversion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handles: tuple[str, ...]
    owner_block_handle: str
    output_kind: TextEntityKind
    text: str
    insertion_point: Point3D
    layer: str
    text_style: str
    text_height: float
    rotation_degrees: float
    erase_source: bool


class AttributeToTextPlan(Batch8Plan):
    command_alias: str = "A2M"
    legacy_symbol: str = "xiAtt2Mt"
    conversions: tuple[AttributeTextConversion, ...]


def plan_attribute_to_text(request: AttributeToTextRequest, attributes: Sequence[AttributeSnapshot]) -> AttributeToTextPlan:
    by_handle = {item.handle.casefold(): item for item in attributes}
    selected = []
    for handle in request.target_handles:
        item = by_handle.get(handle.casefold())
        if item is None:
            raise ValueError(f"attribute not found: {handle}")
        if item.is_xref or item.locked_layer:
            raise ValueError(f"attribute cannot be mutated: {handle}")
        selected.append(item)
    groups: list[list[AttributeSnapshot]]
    if request.mode is AttributeConversionMode.ATTRIBUTE_TO_TEXT:
        groups = [[item] for item in selected]
    else:
        grouped: dict[str, list[AttributeSnapshot]] = {}
        for item in selected:
            grouped.setdefault(item.owner_block_handle.casefold(), []).append(item)
        groups = list(grouped.values())
    conversions = []
    for group in groups:
        values = [f"{item.tag}{request.tag_separator}{item.value}" if request.include_tag else item.value for item in group]
        first = group[0]
        conversions.append(AttributeTextConversion(
            source_handles=tuple(item.handle for item in group), owner_block_handle=first.owner_block_handle,
            output_kind=(TextEntityKind.TEXT if request.mode is AttributeConversionMode.ATTRIBUTE_TO_TEXT else TextEntityKind.MTEXT),
            text=request.block_separator.join(values), insertion_point=first.insertion_point, layer=first.layer,
            text_style=first.text_style, text_height=first.text_height, rotation_degrees=first.rotation_degrees,
            erase_source=request.source_disposition is SourceDisposition.REPLACE))
    return AttributeToTextPlan(document_id=request.document_id, conversions=tuple(conversions), dry_run=request.dry_run)


# ABE -- DCL exposes tag/value edit plus numeric operation or scale, spaces and nested blocks.
class AttributeOperation(StrEnum):
    SET = "set"
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    SCALE = "scale"


class AttributeEditSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    tag: str = Field(min_length=1)
    operation: AttributeOperation
    value: str | Decimal


class AttributeBlockSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    name: str = Field(min_length=1)
    attributes: dict[str, str]
    space: DrawingSpace = DrawingSpace.MODEL
    nested: bool = False
    locked_layer: bool = False
    is_xref: bool = False


class AttributeBlockEditRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_block_handles: tuple[str, ...] = Field(min_length=1)
    edits: tuple[AttributeEditSpec, ...] = Field(min_length=1)
    spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)
    include_nested: bool = False
    missing_tag_policy: str = Field(pattern="^(error|skip)$")
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> AttributeBlockEditRequest:
        _unique(self.target_block_handles, "target_block_handles")
        _unique(tuple(edit.tag for edit in self.edits), "edit tags")
        _approval(self.dry_run, self.approval, "ABE")
        return self


class AttributeValueChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    block_handle: str
    tag: str
    expected_value: str
    replacement_value: str


class AttributeBlockEditPlan(Batch8Plan):
    command_alias: str = "ABE"
    legacy_symbol: str = "xiAttBlkEdit"
    changes: tuple[AttributeValueChange, ...]


def _attribute_value(current: str, edit: AttributeEditSpec) -> str:
    if edit.operation is AttributeOperation.SET:
        return str(edit.value)
    try:
        old = Decimal(current)
        operand = Decimal(edit.value)
    except Exception as exc:
        raise ValueError("ABE numeric operation requires numeric current and operand values") from exc
    if edit.operation is AttributeOperation.ADD:
        result = old + operand
    elif edit.operation is AttributeOperation.SUBTRACT:
        result = old - operand
    elif edit.operation in {AttributeOperation.MULTIPLY, AttributeOperation.SCALE}:
        result = old * operand
    else:
        if operand == 0:
            raise ValueError("ABE division by zero")
        result = old / operand
    return format(result, "f")


def plan_attribute_block_edit(request: AttributeBlockEditRequest, blocks: Sequence[AttributeBlockSnapshot]) -> AttributeBlockEditPlan:
    by_handle = {block.handle.casefold(): block for block in blocks}
    changes = []
    for handle in request.target_block_handles:
        block = by_handle.get(handle.casefold())
        if block is None:
            raise ValueError(f"attribute block not found: {handle}")
        if block.is_xref or block.locked_layer or block.space not in request.spaces or (block.nested and not request.include_nested):
            raise ValueError(f"attribute block is outside requested mutable scope: {handle}")
        tags = {tag.casefold(): (tag, value) for tag, value in block.attributes.items()}
        for edit in request.edits:
            found = tags.get(edit.tag.casefold())
            if found is None:
                if request.missing_tag_policy == "error":
                    raise ValueError(f"attribute tag not found: {edit.tag}")
                continue
            tag, current = found
            changes.append(AttributeValueChange(block_handle=block.handle, tag=tag, expected_value=current,
                                                replacement_value=_attribute_value(current, edit)))
    return AttributeBlockEditPlan(document_id=request.document_id, changes=tuple(changes), dry_run=request.dry_run)


# CTX -- recovered DCL choices are represented directly.
class ContextSelectionPrecedence(StrEnum):
    RANGE_FIRST = "range_first"
    OBJECT_FIRST = "object_first"


class ContextReplacementPolicy(StrEnum):
    FIRST_PER_ENTITY = "first_per_entity"
    ALL_OCCURRENCES = "all_occurrences"
    REPLACE_WHOLE_ENTITY = "replace_whole_entity"


class ContextTextEditRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    old_text: str = Field(min_length=1)
    new_text: str
    selection_precedence: ContextSelectionPrecedence
    whole_string_match: bool
    replacement_policy: ContextReplacementPolicy
    case_sensitive: bool = True
    zoom_text_height_factor: float = Field(gt=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ContextTextEditRequest:
        _approval(self.dry_run, self.approval, "CTX")
        return self


class TextChangesPlan(Batch8Plan):
    changes: tuple[TextChange, ...]


def plan_context_text_edit(request: ContextTextEditRequest, entities: Sequence[TextEntitySnapshot]) -> TextChangesPlan:
    selected = _selected(request.target_handles, entities)
    flags = 0 if request.case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(request.old_text), flags)
    changes = []
    for entity in selected:
        matched = (entity.text == request.old_text if request.case_sensitive else entity.text.casefold() == request.old_text.casefold()) if request.whole_string_match else pattern.search(entity.text) is not None
        if not matched:
            continue
        if request.replacement_policy is ContextReplacementPolicy.REPLACE_WHOLE_ENTITY:
            replacement = request.new_text
        else:
            count = 1 if request.replacement_policy is ContextReplacementPolicy.FIRST_PER_ENTITY else 0
            replacement = pattern.sub(lambda _: request.new_text, entity.text, count=count)
        changes.append(TextChange(handle=entity.handle, expected_text=entity.text, replacement_text=replacement))
    return TextChangesPlan(command_alias="CTX", legacy_symbol="xiCTX", document_id=request.document_id,
                           changes=tuple(changes), dry_run=request.dry_run)


# TC -- shortcut explicitly says copy text OR place it in an Acad table.
class TextCopyDestination(StrEnum):
    NEW_TEXT = "new_text"
    TABLE_CELL = "table_cell"


class TextCopyPlacement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    destination: TextCopyDestination
    insertion_point: Point3D | None = None
    table_handle: str | None = None
    row: int | None = Field(default=None, ge=0)
    column: int | None = Field(default=None, ge=0)
    expected_cell_text: str | None = None

    @model_validator(mode="after")
    def validate_destination(self) -> TextCopyPlacement:
        if self.destination is TextCopyDestination.NEW_TEXT and self.insertion_point is None:
            raise ValueError("TC new_text destination requires insertion_point")
        if self.destination is TextCopyDestination.TABLE_CELL and (not self.table_handle or self.row is None or self.column is None or self.expected_cell_text is None):
            raise ValueError("TC table_cell destination requires table handle, row, column and expected text")
        return self


class TextCopyRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    placements: tuple[TextCopyPlacement, ...] = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TextCopyRequest:
        _approval(self.dry_run, self.approval, "TC")
        return self


class TableCellChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    table_handle: str
    row: int
    column: int
    expected_text: str
    replacement_text: str


class TextCopyPlan(Batch8Plan):
    command_alias: str = "TC"
    legacy_symbol: str = "xiTextCopy"
    creates: tuple[TextWriteSpec, ...]
    table_changes: tuple[TableCellChange, ...]


def plan_text_copy(request: TextCopyRequest, entities: Sequence[TextEntitySnapshot]) -> TextCopyPlan:
    by_handle = {entity.handle.casefold(): entity for entity in entities}
    if len(by_handle) != len(entities):
        raise ValueError("entity handles must be unique")
    sources = []
    for placement in request.placements:
        source = by_handle.get(placement.source_handle.casefold())
        if source is None:
            raise ValueError(f"text entity not found: {placement.source_handle}")
        if source.is_xref or source.locked_layer:
            raise ValueError(f"text entity cannot be mutated: {placement.source_handle}")
        sources.append(source)
    creates, cells = [], []
    for placement, source in zip(request.placements, sources, strict=True):
        if placement.destination is TextCopyDestination.NEW_TEXT:
            creates.append(TextWriteSpec(text=source.text, insertion_point=placement.insertion_point, layer=source.layer,
                                         text_style=source.text_style, text_height=source.text_height,
                                         rotation_degrees=source.rotation_degrees))
        else:
            cells.append(TableCellChange(table_handle=placement.table_handle, row=placement.row, column=placement.column,
                                         expected_text=placement.expected_cell_text, replacement_text=source.text))
    return TextCopyPlan(document_id=request.document_id, creates=tuple(creates), table_changes=tuple(cells),
                        dry_run=request.dry_run)


# TE -- broad "comprehensive edit" is intentionally represented as an explicit patch.
class ComprehensiveTextPatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    expected_text: str | None = None
    replacement_text: str | None = None
    target_layer: str | None = None
    target_style: str | None = None
    text_height: float | None = Field(default=None, gt=0)
    width_factor: float | None = Field(default=None, gt=0, le=100)
    rotation_degrees: float | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> ComprehensiveTextPatch:
        values = (self.replacement_text, self.target_layer, self.target_style, self.text_height,
                  self.width_factor, self.rotation_degrees)
        if all(value is None for value in values):
            raise ValueError("TE patch must change at least one property")
        if self.rotation_degrees is not None and not isfinite(self.rotation_degrees):
            raise ValueError("rotation_degrees must be finite")
        return self


class ComprehensiveTextEditRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    patches: tuple[ComprehensiveTextPatch, ...] = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> ComprehensiveTextEditRequest:
        _unique(tuple(p.handle for p in self.patches), "patch handles")
        _approval(self.dry_run, self.approval, "TE")
        return self


class TextPropertyChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_text: str
    replacement_text: str | None
    target_layer: str | None
    target_style: str | None
    text_height: float | None
    width_factor: float | None
    rotation_degrees: float | None


class ComprehensiveTextEditPlan(Batch8Plan):
    command_alias: str = "TE"
    legacy_symbol: str = "xiTextEdit"
    changes: tuple[TextPropertyChange, ...]


def plan_comprehensive_text_edit(request: ComprehensiveTextEditRequest, entities: Sequence[TextEntitySnapshot]) -> ComprehensiveTextEditPlan:
    selected = _selected(tuple(p.handle for p in request.patches), entities)
    changes = []
    for patch, entity in zip(request.patches, selected, strict=True):
        if patch.expected_text is not None and patch.expected_text != entity.text:
            raise ValueError(f"TE expected text mismatch: {entity.handle}")
        changes.append(TextPropertyChange(handle=entity.handle, expected_text=entity.text,
            replacement_text=patch.replacement_text, target_layer=patch.target_layer, target_style=patch.target_style,
            text_height=patch.text_height, width_factor=patch.width_factor, rotation_degrees=patch.rotation_degrees))
    return ComprehensiveTextEditPlan(document_id=request.document_id, changes=tuple(changes), dry_run=request.dry_run)


# TFF -- the geometry-derived extents are supplied, not guessed by the planner.
class MTextFrameSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    current_width: float = Field(gt=0)
    measured_content_width: float = Field(gt=0)
    text_height: float = Field(gt=0)
    locked_layer: bool = False
    is_xref: bool = False


class FrameFitMode(StrEnum):
    TIGHT = "tight"
    HEIGHT_MULTIPLE_PADDING = "height_multiple_padding"


class MTextFrameFitRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    mode: FrameFitMode
    horizontal_padding_height_factor: float = Field(default=0, ge=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> MTextFrameFitRequest:
        _unique(self.target_handles, "target_handles")
        _approval(self.dry_run, self.approval, "TFF")
        return self


class MTextWidthChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_width: float
    replacement_width: float = Field(gt=0)


class MTextFrameFitPlan(Batch8Plan):
    command_alias: str = "TFF"
    legacy_symbol: str = "xiTextFrameFix"
    changes: tuple[MTextWidthChange, ...]


def plan_mtext_frame_fit(request: MTextFrameFitRequest, frames: Sequence[MTextFrameSnapshot]) -> MTextFrameFitPlan:
    by_handle = {f.handle.casefold(): f for f in frames}
    changes = []
    for handle in request.target_handles:
        frame = by_handle.get(handle.casefold())
        if frame is None or frame.is_xref or frame.locked_layer:
            raise ValueError(f"mtext frame cannot be mutated: {handle}")
        padding = 0 if request.mode is FrameFitMode.TIGHT else request.horizontal_padding_height_factor * frame.text_height * 2
        changes.append(MTextWidthChange(handle=frame.handle, expected_width=frame.current_width,
                                        replacement_width=frame.measured_content_width + padding))
    return MTextFrameFitPlan(document_id=request.document_id, changes=tuple(changes), dry_run=request.dry_run)


# TO/TOA -- bounding geometry is normalized into explicit center/inside points.
class ContainerSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    center: Point3D
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class TextContainerPair(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text_handle: str = Field(min_length=1)
    container_handle: str = Field(min_length=1)


class ContainerAlignment(StrEnum):
    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"


class TextCenterRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    pairs: tuple[TextContainerPair, ...] = Field(min_length=1)
    alignment: ContainerAlignment = ContainerAlignment.CENTER
    horizontal_margin_height_factor: float = Field(default=0, ge=0)
    line_gap_height_factor: float = Field(default=1, ge=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TextCenterRequest:
        _unique(tuple(p.text_handle for p in self.pairs), "text handles")
        _approval(self.dry_run, self.approval, "TO/TOA")
        return self


class MoveSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    from_point: Point3D
    to_point: Point3D


class TextCenterPlan(Batch8Plan):
    moves: tuple[MoveSpec, ...]
    alignment: ContainerAlignment
    horizontal_margin_height_factor: float
    line_gap_height_factor: float


def plan_text_center(request: TextCenterRequest, entities: Sequence[TextEntitySnapshot], containers: Sequence[ContainerSnapshot], *, alias: str) -> TextCenterPlan:
    if alias not in {"TO", "TOA"}:
        raise ValueError("alias must be TO or TOA")
    texts = {e.handle.casefold(): e for e in _selected(tuple(p.text_handle for p in request.pairs), entities)}
    boxes = {b.handle.casefold(): b for b in containers}
    resolved = []
    for pair in request.pairs:
        text, box = texts[pair.text_handle.casefold()], boxes.get(pair.container_handle.casefold())
        if box is None:
            raise ValueError(f"container not found: {pair.container_handle}")
        resolved.append((text, box))
    container_counts: dict[str, int] = {}
    container_indices: dict[str, int] = {}
    for pair in request.pairs:
        key = pair.container_handle.casefold()
        container_counts[key] = container_counts.get(key, 0) + 1
    moves = []
    for pair, (text, box) in zip(request.pairs, resolved, strict=True):
        key = pair.container_handle.casefold()
        index = container_indices.get(key, 0)
        container_indices[key] = index + 1
        margin = request.horizontal_margin_height_factor * text.text_height
        x = box.center.x
        if request.alignment is ContainerAlignment.LEFT:
            x = box.center.x - box.width / 2 + margin
        elif request.alignment is ContainerAlignment.RIGHT:
            x = box.center.x + box.width / 2 - margin
        y = box.center.y + ((container_counts[key] - 1) / 2 - index) * request.line_gap_height_factor * text.text_height
        moves.append(MoveSpec(handle=text.handle, from_point=text.insertion_point,
                              to_point=Point3D(x=x, y=y, z=box.center.z)))
    return TextCenterPlan(command_alias=alias, legacy_symbol="xiText2Center" if alias == "TO" else "xiTextOfAlign",
                          document_id=request.document_id, moves=tuple(moves), alignment=request.alignment,
                          horizontal_margin_height_factor=request.horizontal_margin_height_factor,
                          line_gap_height_factor=request.line_gap_height_factor, dry_run=request.dry_run)


# TSH -- shadow representation is explicit rather than inferred.
class ShadowRepresentation(StrEnum):
    TEXT_COPY = "text_copy"
    SOLID_OUTLINE = "solid_outline"


class TextShadowRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    representation: ShadowRepresentation
    offset: Point3D
    layer: str = Field(min_length=1)
    color_index: int = Field(ge=1, le=255)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TextShadowRequest:
        _approval(self.dry_run, self.approval, "TSH")
        return self


class ShadowSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    representation: ShadowRepresentation
    insertion_point: Point3D
    layer: str
    color_index: int


class TextShadowPlan(Batch8Plan):
    command_alias: str = "TSH"
    legacy_symbol: str = "xiTextShadow"
    shadows: tuple[ShadowSpec, ...]


def plan_text_shadow(request: TextShadowRequest, entities: Sequence[TextEntitySnapshot]) -> TextShadowPlan:
    selected = _selected(request.target_handles, entities)
    return TextShadowPlan(document_id=request.document_id, shadows=tuple(ShadowSpec(
        source_handle=e.handle, representation=request.representation,
        insertion_point=Point3D(x=e.insertion_point.x + request.offset.x, y=e.insertion_point.y + request.offset.y,
                                z=e.insertion_point.z + request.offset.z),
        layer=request.layer, color_index=request.color_index) for e in selected), dry_run=request.dry_run)


# TSM -- recovered DCL: multiple source styles, one target style, optional removal.
class StyleMergeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_styles: tuple[str, ...] = Field(min_length=1)
    target_style: str = Field(min_length=1)
    remove_source_styles: bool
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> StyleMergeRequest:
        _unique(self.source_styles, "source_styles")
        if self.target_style.casefold() in {s.casefold() for s in self.source_styles}:
            raise ValueError("TSM target style cannot be a source style")
        _approval(self.dry_run, self.approval, "TSM")
        return self


class StyleMergePlan(Batch8Plan):
    command_alias: str = "TSM"
    legacy_symbol: str = "xiStyleMerge"
    changes: tuple[TextChange, ...]
    entity_style_changes: dict[str, str]
    remove_style_names: tuple[str, ...]


def plan_style_merge(request: StyleMergeRequest, entities: Sequence[TextEntitySnapshot]) -> StyleMergePlan:
    sources = {style.casefold() for style in request.source_styles}
    affected = {e.handle: request.target_style for e in entities if e.text_style.casefold() in sources and not e.is_xref}
    if any(e.locked_layer for e in entities if e.handle in affected):
        raise ValueError("TSM affected entity is on a locked layer")
    return StyleMergePlan(document_id=request.document_id, changes=(), entity_style_changes=affected,
                          remove_style_names=request.source_styles if request.remove_source_styles else (),
                          dry_run=request.dry_run)


# DAT -- dynamic title is represented by an explicit CAD field expression.
class DynamicTitleRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    field_expression: str = Field(min_length=1)
    preview_text: str = Field(min_length=1)
    insertion_point: Point3D
    layer: str = Field(min_length=1)
    text_style: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> DynamicTitleRequest:
        if "%<" not in self.field_expression or ">%" not in self.field_expression:
            raise ValueError("DAT field_expression must be an explicit CAD field expression")
        _approval(self.dry_run, self.approval, "DAT")
        return self


class DynamicTitlePlan(Batch8Plan):
    command_alias: str = "DAT"
    legacy_symbol: str = "xiDyTitle"
    field_expression: str
    preview: TextWriteSpec


def plan_dynamic_title(request: DynamicTitleRequest) -> DynamicTitlePlan:
    return DynamicTitlePlan(document_id=request.document_id, field_expression=request.field_expression,
        preview=TextWriteSpec(text=request.preview_text, insertion_point=request.insertion_point, layer=request.layer,
                              text_style=request.text_style, text_height=request.text_height), dry_run=request.dry_run)


# LTX -- equally spaced text uses an explicit sequence and direction vector.
class EqualSpacingTextRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    texts: tuple[str, ...] = Field(min_length=1)
    start_point: Point3D
    step_vector: Point3D
    layer: str = Field(min_length=1)
    text_style: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    rotation_degrees: float = 0
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> EqualSpacingTextRequest:
        if self.step_vector == Point3D(x=0, y=0, z=0):
            raise ValueError("LTX step_vector must be non-zero")
        _approval(self.dry_run, self.approval, "LTX")
        return self


class EqualSpacingTextPlan(Batch8Plan):
    command_alias: str = "LTX"
    legacy_symbol: str = "xiLText"
    creates: tuple[TextWriteSpec, ...]


def plan_equal_spacing_text(request: EqualSpacingTextRequest) -> EqualSpacingTextPlan:
    creates = tuple(TextWriteSpec(text=text,
        insertion_point=Point3D(x=request.start_point.x + request.step_vector.x * index,
                                y=request.start_point.y + request.step_vector.y * index,
                                z=request.start_point.z + request.step_vector.z * index),
        layer=request.layer, text_style=request.text_style, text_height=request.text_height,
        rotation_degrees=request.rotation_degrees) for index, text in enumerate(request.texts))
    return EqualSpacingTextPlan(document_id=request.document_id, creates=creates, dry_run=request.dry_run)


def register_headless_core_batch8_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(title="xiCAD Headless Core Batch 8 Planner", readOnlyHint=True,
                                destructiveHint=False, idempotentHint=True, openWorldHint=False)

    @mcp.tool(name="xicad_plan_a2m", annotations=read_only)
    def mcp_plan_a2m(request: AttributeToTextRequest, attributes: tuple[AttributeSnapshot, ...]) -> AttributeToTextPlan:
        return plan_attribute_to_text(request, attributes)

    @mcp.tool(name="xicad_plan_abe", annotations=read_only)
    def mcp_plan_abe(request: AttributeBlockEditRequest, blocks: tuple[AttributeBlockSnapshot, ...]) -> AttributeBlockEditPlan:
        return plan_attribute_block_edit(request, blocks)

    @mcp.tool(name="xicad_plan_ctx", annotations=read_only)
    def mcp_plan_ctx(request: ContextTextEditRequest, entities: tuple[TextEntitySnapshot, ...]) -> TextChangesPlan:
        return plan_context_text_edit(request, entities)

    @mcp.tool(name="xicad_plan_tc", annotations=read_only)
    def mcp_plan_tc(request: TextCopyRequest, entities: tuple[TextEntitySnapshot, ...]) -> TextCopyPlan:
        return plan_text_copy(request, entities)

    @mcp.tool(name="xicad_plan_te", annotations=read_only)
    def mcp_plan_te(request: ComprehensiveTextEditRequest, entities: tuple[TextEntitySnapshot, ...]) -> ComprehensiveTextEditPlan:
        return plan_comprehensive_text_edit(request, entities)

    @mcp.tool(name="xicad_plan_tff", annotations=read_only)
    def mcp_plan_tff(request: MTextFrameFitRequest, frames: tuple[MTextFrameSnapshot, ...]) -> MTextFrameFitPlan:
        return plan_mtext_frame_fit(request, frames)

    @mcp.tool(name="xicad_plan_to", annotations=read_only)
    def mcp_plan_to(request: TextCenterRequest, entities: tuple[TextEntitySnapshot, ...], containers: tuple[ContainerSnapshot, ...]) -> TextCenterPlan:
        return plan_text_center(request, entities, containers, alias="TO")

    @mcp.tool(name="xicad_plan_toa", annotations=read_only)
    def mcp_plan_toa(request: TextCenterRequest, entities: tuple[TextEntitySnapshot, ...], containers: tuple[ContainerSnapshot, ...]) -> TextCenterPlan:
        return plan_text_center(request, entities, containers, alias="TOA")

    @mcp.tool(name="xicad_plan_tsh", annotations=read_only)
    def mcp_plan_tsh(request: TextShadowRequest, entities: tuple[TextEntitySnapshot, ...]) -> TextShadowPlan:
        return plan_text_shadow(request, entities)

    @mcp.tool(name="xicad_plan_tsm", annotations=read_only)
    def mcp_plan_tsm(request: StyleMergeRequest, entities: tuple[TextEntitySnapshot, ...]) -> StyleMergePlan:
        return plan_style_merge(request, entities)

    @mcp.tool(name="xicad_plan_dat", annotations=read_only)
    def mcp_plan_dat(request: DynamicTitleRequest) -> DynamicTitlePlan:
        return plan_dynamic_title(request)

    @mcp.tool(name="xicad_plan_ltx", annotations=read_only)
    def mcp_plan_ltx(request: EqualSpacingTextRequest) -> EqualSpacingTextPlan:
        return plan_equal_spacing_text(request)
