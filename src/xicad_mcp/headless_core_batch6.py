from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from enum import StrEnum
from math import dist, isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D
from .headless_core_batch5 import (
    TextChange,
    TextEntityKind,
    TextEntitySnapshot,
    TextWriteSpec,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class Batch6RoundingMode(StrEnum):
    FLOOR = "floor"
    HALF_UP = "half_up"
    CEILING = "ceiling"


_ROUNDING = {
    Batch6RoundingMode.FLOOR: ROUND_FLOOR,
    Batch6RoundingMode.HALF_UP: ROUND_HALF_UP,
    Batch6RoundingMode.CEILING: ROUND_CEILING,
}


def _quantize(value: Decimal, places: int, rounding: Batch6RoundingMode) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=_ROUNDING[rounding])


def _format_decimal(
    value: Decimal,
    places: int,
    rounding: Batch6RoundingMode,
    thousands_separator: bool = False,
    force_plus: bool = False,
) -> str:
    rounded = _quantize(value, places, rounding)
    rendered = f"{rounded:,.{places}f}" if thousands_separator else f"{rounded:.{places}f}"
    if force_plus and rounded >= 0:
        rendered = "+" + rendered
    return rendered


def _require_mutation_approval(dry_run: bool, approval: Approval, command: str) -> None:
    if not dry_run and not approval.approved:
        raise ValueError(f"{command} execution requires explicit approval")


def _unique(values: Sequence[str], field_name: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{field_name} must be unique")


def _entity_map(entities: Sequence[TextEntitySnapshot]) -> dict[str, TextEntitySnapshot]:
    result: dict[str, TextEntitySnapshot] = {}
    for entity in entities:
        key = entity.handle.casefold()
        if key in result:
            raise ValueError(f"duplicate text handle: {entity.handle}")
        result[key] = entity
    return result


def _select_mutable_texts(
    handles: Sequence[str], entities: Sequence[TextEntitySnapshot]
) -> tuple[TextEntitySnapshot, ...]:
    _unique(handles, "target_handles")
    by_handle = _entity_map(entities)
    selected: list[TextEntitySnapshot] = []
    for handle in handles:
        entity = by_handle.get(handle.casefold())
        if entity is None:
            raise ValueError(f"text entity not found: {handle}")
        if entity.is_xref:
            raise ValueError(f"xref text cannot be mutated: {handle}")
        if entity.locked_layer:
            raise ValueError(f"locked-layer text cannot be mutated: {handle}")
        selected.append(entity)
    return tuple(selected)


_NUMERIC_TOKEN = re.compile(r"(?<![\d.])(?P<open>\()?(?P<sign>[+-]?)(?P<num>\d+(?:\.\d+)?)(?P<close>\))?(?![\d.])")


def _numeric_matches(text: str) -> list[re.Match[str]]:
    return list(_NUMERIC_TOKEN.finditer(text))


def _replace_numeric_match(
    text: str,
    match: re.Match[str],
    value: Decimal,
    decimal_places: int,
    rounding: Batch6RoundingMode,
    preserve_plus: bool,
) -> str:
    parenthesized_negative = bool(match.group("open") and match.group("close") and not match.group("sign"))
    force_plus = preserve_plus and match.group("sign") == "+"
    rendered = _format_decimal(
        abs(value) if parenthesized_negative else value, decimal_places, rounding, force_plus=force_plus
    )
    if parenthesized_negative:
        rendered = f"({rendered})"
    return text[: match.start()] + rendered + text[match.end() :]


# ---------------------------------------------------------------------------
# M2 / xiM2 — pyeong to square metres
# ---------------------------------------------------------------------------


class AreaOutputMode(StrEnum):
    RETURN_ONLY = "return_only"
    UPDATE_TARGET = "update_target"
    CREATE_NEW = "create_new"


class PyeongInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    pyeong: Decimal
    source_handle: str | None = None
    target_handle: str | None = None
    insertion_point: Point3D | None = None


class PyeongToSquareMetreRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    inputs: tuple[PyeongInput, ...] = Field(min_length=1)
    output_mode: AreaOutputMode
    decimal_places: int = Field(ge=0, le=12)
    rounding_mode: Batch6RoundingMode
    thousands_separator: bool = False
    unit_text: str = " ㎡"
    include_parentheses: bool = False
    output_layer: str = Field(default="TEXT", min_length=1)
    output_text_style: str = Field(default="Standard", min_length=1)
    output_text_height: float = Field(default=2.5, gt=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_output_targets(self) -> PyeongToSquareMetreRequest:
        for item in self.inputs:
            if self.output_mode is AreaOutputMode.UPDATE_TARGET and not item.target_handle:
                raise ValueError("M2 update_target requires target_handle for every input")
            if self.output_mode is AreaOutputMode.CREATE_NEW and item.insertion_point is None:
                raise ValueError("M2 create_new requires insertion_point for every input")
        if self.output_mode is not AreaOutputMode.RETURN_ONLY:
            _require_mutation_approval(self.dry_run, self.approval, "M2")
        return self


class AreaConversionOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str | None
    target_handle: str | None
    pyeong: Decimal
    exact_square_metres: Decimal
    rounded_square_metres: Decimal
    rendered_text: str
    create_spec: TextWriteSpec | None = None


class PyeongToSquareMetrePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "M2"
    legacy_symbol: str = "xiM2"
    document_id: str
    output_mode: AreaOutputMode
    outputs: tuple[AreaConversionOutput, ...]
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def plan_pyeong_to_square_metres(request: PyeongToSquareMetreRequest) -> PyeongToSquareMetrePlan:
    outputs: list[AreaConversionOutput] = []
    for item in request.inputs:
        exact = item.pyeong / Decimal("0.3025")
        rounded = _quantize(exact, request.decimal_places, request.rounding_mode)
        rendered = (
            _format_decimal(
                exact,
                request.decimal_places,
                request.rounding_mode,
                request.thousands_separator,
            )
            + request.unit_text
        )
        if request.include_parentheses:
            rendered = f"({rendered})"
        create_spec = None
        if request.output_mode is AreaOutputMode.CREATE_NEW:
            create_spec = TextWriteSpec(
                text=rendered,
                insertion_point=item.insertion_point,
                layer=request.output_layer,
                text_style=request.output_text_style,
                text_height=request.output_text_height,
            )
        outputs.append(
            AreaConversionOutput(
                source_handle=item.source_handle,
                target_handle=item.target_handle,
                pyeong=item.pyeong,
                exact_square_metres=exact,
                rounded_square_metres=rounded,
                rendered_text=rendered,
                create_spec=create_spec,
            )
        )
    return PyeongToSquareMetrePlan(
        document_id=request.document_id,
        output_mode=request.output_mode,
        outputs=tuple(outputs),
        dry_run=request.dry_run,
    )


# ---------------------------------------------------------------------------
# INA / SPN — normalized symbol-number aggregation
# ---------------------------------------------------------------------------


class AggregateSourceKind(StrEnum):
    TEXT_PAIR = "text_pair"
    ATTRIBUTE_BLOCK = "attribute_block"
    NORMALIZED_INPUT = "normalized_input"


class SymbolNumberRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    symbol: str = Field(min_length=1)
    quantity: Decimal
    source_handles: tuple[str, ...] = ()


class AggregateLayout(StrEnum):
    ONE_TEXT = "one_text"
    TWO_TEXTS = "two_texts"


class SymbolAggregateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    records: tuple[SymbolNumberRecord, ...] = Field(min_length=1)
    source_kind: AggregateSourceKind
    layout: AggregateLayout
    separator: str = " / "
    decimal_places: int = Field(default=0, ge=0, le=12)
    rounding_mode: Batch6RoundingMode = Batch6RoundingMode.HALF_UP
    store_recalculation_metadata: bool = False
    output_layer: str = Field(default="TEXT", min_length=1)
    insertion_point: Point3D | None = None
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> SymbolAggregateRequest:
        if self.insertion_point is not None:
            _require_mutation_approval(self.dry_run, self.approval, "INA/SPN")
        return self


class SymbolAggregateRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    symbol: str
    total: Decimal
    rendered_total: str
    source_handles: tuple[str, ...]


class SymbolAggregatePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    rows: tuple[SymbolAggregateRow, ...]
    rendered_texts: tuple[str, ...]
    store_recalculation_metadata: bool
    create_specs: tuple[TextWriteSpec, ...]
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def plan_symbol_aggregate(
    request: SymbolAggregateRequest,
    *,
    command_alias: str,
) -> SymbolAggregatePlan:
    if command_alias not in {"INA", "SPN"}:
        raise ValueError("command_alias must be INA or SPN")
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    handles: dict[str, list[str]] = defaultdict(list)
    spelling: dict[str, str] = {}
    order: list[str] = []
    for record in request.records:
        key = record.symbol.casefold()
        if key not in spelling:
            spelling[key] = record.symbol
            order.append(key)
        totals[key] += record.quantity
        handles[key].extend(record.source_handles)
    rows: list[SymbolAggregateRow] = []
    rendered: list[str] = []
    for key in order:
        rendered_total = _format_decimal(totals[key], request.decimal_places, request.rounding_mode)
        rows.append(
            SymbolAggregateRow(
                symbol=spelling[key],
                total=totals[key],
                rendered_total=rendered_total,
                source_handles=tuple(handles[key]),
            )
        )
        if request.layout is AggregateLayout.ONE_TEXT:
            rendered.append(f"{spelling[key]}{request.separator}{rendered_total}")
        else:
            rendered.extend((spelling[key], rendered_total))
    create_specs: list[TextWriteSpec] = []
    if request.insertion_point is not None:
        for index, text in enumerate(rendered):
            create_specs.append(
                TextWriteSpec(
                    text=text,
                    insertion_point=Point3D(
                        x=request.insertion_point.x,
                        y=request.insertion_point.y - index * 3.0,
                        z=request.insertion_point.z,
                    ),
                    layer=request.output_layer,
                    text_style="Standard",
                    text_height=2.5,
                )
            )
    return SymbolAggregatePlan(
        command_alias=command_alias,
        legacy_symbol="xiIndexNumAdd" if command_alias == "INA" else "xiSumPairNum",
        document_id=request.document_id,
        rows=tuple(rows),
        rendered_texts=tuple(rendered),
        store_recalculation_metadata=request.store_recalculation_metadata,
        create_specs=tuple(create_specs),
        dry_run=request.dry_run,
    )


# ---------------------------------------------------------------------------
# LIS / xiLineSum — normalized curve-length summation
# ---------------------------------------------------------------------------


class CurveKind(StrEnum):
    LINE = "line"
    POLYLINE = "polyline"
    ARC = "arc"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    SPLINE = "spline"


class CurveLengthSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    kind: CurveKind
    layer: str = Field(min_length=1)
    length_drawing_units: Decimal = Field(gt=0)
    vertex_segment_lengths: tuple[Decimal, ...] = ()
    locked_layer: bool = False
    is_xref: bool = False

    @model_validator(mode="after")
    def validate_segments(self) -> CurveLengthSnapshot:
        if any(value <= 0 for value in self.vertex_segment_lengths):
            raise ValueError("vertex segment lengths must be positive")
        return self


class LengthUnit(StrEnum):
    MILLIMETRE = "mm"
    METRE = "m"


class LineSumRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    output_unit: LengthUnit
    drawing_units_per_millimetre: Decimal = Field(default=Decimal(1), gt=0)
    decimal_places: int = Field(default=0, ge=0, le=12)
    rounding_mode: Batch6RoundingMode = Batch6RoundingMode.HALF_UP
    thousands_separator: bool = False
    show_unit: bool = True
    blank_before_unit: bool = False
    include_equal_sign: bool = True
    include_formula: bool = False
    group_by_layer: bool = False
    include_vertex_segments: bool = False
    live_field_requested: bool = False
    output_insertion_point: Point3D | None = None
    output_layer: str = Field(default="TEXT", min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> LineSumRequest:
        _unique(self.target_handles, "target_handles")
        if self.output_insertion_point is not None:
            _require_mutation_approval(self.dry_run, self.approval, "LIS")
        return self


class LayerLengthTotal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    layer: str
    total: Decimal


class LineSumPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "LIS"
    legacy_symbol: str = "xiLineSum"
    document_id: str
    selected_handles: tuple[str, ...]
    total_drawing_units: Decimal
    total_output_units: Decimal
    layer_totals: tuple[LayerLengthTotal, ...]
    formula: str | None
    rendered_text: str
    live_field_requested: bool
    create_spec: TextWriteSpec | None
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def plan_line_sum(request: LineSumRequest, curves: Sequence[CurveLengthSnapshot]) -> LineSumPlan:
    by_handle = {curve.handle.casefold(): curve for curve in curves}
    selected: list[CurveLengthSnapshot] = []
    for handle in request.target_handles:
        curve = by_handle.get(handle.casefold())
        if curve is None:
            raise ValueError(f"curve not found: {handle}")
        if curve.is_xref:
            raise ValueError(f"xref curve is unsupported: {handle}")
        selected.append(curve)
    total_drawing = sum((curve.length_drawing_units for curve in selected), Decimal(0))
    divisor = request.drawing_units_per_millimetre
    total_mm = total_drawing / divisor
    total_output = total_mm if request.output_unit is LengthUnit.MILLIMETRE else total_mm / Decimal(1000)
    layer_raw: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    for curve in selected:
        layer_raw[curve.layer] += curve.length_drawing_units
    layer_totals = (
        tuple(
            LayerLengthTotal(
                layer=layer,
                total=(
                    value / divisor if request.output_unit is LengthUnit.MILLIMETRE else value / divisor / Decimal(1000)
                ),
            )
            for layer, value in sorted(layer_raw.items())
        )
        if request.group_by_layer
        else ()
    )
    parts = [
        _format_decimal(
            (
                curve.length_drawing_units / divisor
                if request.output_unit is LengthUnit.MILLIMETRE
                else curve.length_drawing_units / divisor / Decimal(1000)
            ),
            request.decimal_places,
            request.rounding_mode,
            request.thousands_separator,
        )
        for curve in selected
    ]
    if request.include_vertex_segments:
        for curve in selected:
            parts.extend(
                _format_decimal(
                    (
                        segment / divisor
                        if request.output_unit is LengthUnit.MILLIMETRE
                        else segment / divisor / Decimal(1000)
                    ),
                    request.decimal_places,
                    request.rounding_mode,
                    request.thousands_separator,
                )
                for segment in curve.vertex_segment_lengths
            )
    formula = " + ".join(parts) if request.include_formula else None
    total_text = _format_decimal(
        total_output,
        request.decimal_places,
        request.rounding_mode,
        request.thousands_separator,
    )
    if request.include_equal_sign:
        total_text = "= " + total_text
    if request.show_unit:
        total_text += (" " if request.blank_before_unit else "") + request.output_unit.value
    rendered = f"{formula} {total_text}" if formula else total_text
    create_spec = None
    if request.output_insertion_point is not None:
        create_spec = TextWriteSpec(
            text=rendered,
            insertion_point=request.output_insertion_point,
            layer=request.output_layer,
            text_style="Standard",
            text_height=2.5,
        )
    return LineSumPlan(
        document_id=request.document_id,
        selected_handles=request.target_handles,
        total_drawing_units=total_drawing,
        total_output_units=total_output,
        layer_totals=layer_totals,
        formula=formula,
        rendered_text=rendered,
        live_field_requested=request.live_field_requested,
        create_spec=create_spec,
        dry_run=request.dry_run,
    )


# ---------------------------------------------------------------------------
# LMA / LNA — level number transformations
# ---------------------------------------------------------------------------


class LevelMoveMode(StrEnum):
    MOVE = "move"
    COPY = "copy"


class LevelNumberPolicy(StrEnum):
    FIRST = "first"
    LAST = "last"


class LevelMoveAddRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    mode: LevelMoveMode
    translation: Point3D
    level_delta: Decimal
    number_policy: LevelNumberPolicy = LevelNumberPolicy.LAST
    decimal_places: int = Field(default=2, ge=0, le=12)
    rounding_mode: Batch6RoundingMode = Batch6RoundingMode.HALF_UP
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> LevelMoveAddRequest:
        _unique(self.target_handles, "target_handles")
        _require_mutation_approval(self.dry_run, self.approval, "LMA")
        return self


class LevelNumberAddRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    delta: Decimal
    number_policy: LevelNumberPolicy = LevelNumberPolicy.LAST
    decimal_places: int = Field(default=2, ge=0, le=12)
    rounding_mode: Batch6RoundingMode = Batch6RoundingMode.HALF_UP
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> LevelNumberAddRequest:
        _unique(self.target_handles, "target_handles")
        _require_mutation_approval(self.dry_run, self.approval, "LNA")
        return self


class LevelTransformPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    text_changes: tuple[TextChange, ...]
    create_specs: tuple[TextWriteSpec, ...]
    move_handles: tuple[str, ...]
    translation: Point3D | None
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def _level_replacement(
    entity: TextEntitySnapshot,
    delta: Decimal,
    policy: LevelNumberPolicy,
    decimal_places: int,
    rounding: Batch6RoundingMode,
) -> str:
    matches = _numeric_matches(entity.text)
    if not matches:
        raise ValueError(f"level text has no numeric token: {entity.handle}")
    match = matches[0] if policy is LevelNumberPolicy.FIRST else matches[-1]
    original = Decimal(match.group("num"))
    if match.group("sign") == "-" or (match.group("open") and match.group("close") and not match.group("sign")):
        original = -original
    return _replace_numeric_match(
        entity.text,
        match,
        original + delta,
        decimal_places,
        rounding,
        preserve_plus=True,
    )


def plan_level_move_add(
    request: LevelMoveAddRequest,
    entities: Sequence[TextEntitySnapshot],
) -> LevelTransformPlan:
    selected = _select_mutable_texts(request.target_handles, entities)
    changes: list[TextChange] = []
    creates: list[TextWriteSpec] = []
    for entity in selected:
        replacement = _level_replacement(
            entity, request.level_delta, request.number_policy, request.decimal_places, request.rounding_mode
        )
        if request.mode is LevelMoveMode.MOVE:
            changes.append(TextChange(handle=entity.handle, expected_text=entity.text, replacement_text=replacement))
        else:
            creates.append(
                TextWriteSpec(
                    text=replacement,
                    insertion_point=Point3D(
                        x=entity.insertion_point.x + request.translation.x,
                        y=entity.insertion_point.y + request.translation.y,
                        z=entity.insertion_point.z + request.translation.z,
                    ),
                    layer=entity.layer,
                    text_style=entity.text_style,
                    text_height=entity.text_height,
                    rotation_degrees=entity.rotation_degrees,
                )
            )
    return LevelTransformPlan(
        command_alias="LMA",
        legacy_symbol="xiLevelMoveAdd",
        document_id=request.document_id,
        text_changes=tuple(changes),
        create_specs=tuple(creates),
        move_handles=request.target_handles if request.mode is LevelMoveMode.MOVE else (),
        translation=request.translation,
        dry_run=request.dry_run,
    )


def plan_level_number_add(
    request: LevelNumberAddRequest,
    entities: Sequence[TextEntitySnapshot],
) -> LevelTransformPlan:
    selected = _select_mutable_texts(request.target_handles, entities)
    changes = tuple(
        TextChange(
            handle=entity.handle,
            expected_text=entity.text,
            replacement_text=_level_replacement(
                entity, request.delta, request.number_policy, request.decimal_places, request.rounding_mode
            ),
        )
        for entity in selected
    )
    return LevelTransformPlan(
        command_alias="LNA",
        legacy_symbol="xiLevelNumAdd",
        document_id=request.document_id,
        text_changes=changes,
        create_specs=(),
        move_handles=(),
        translation=None,
        dry_run=request.dry_run,
    )


# ---------------------------------------------------------------------------
# QD / xiQuickDist — explicit point-distance plan
# ---------------------------------------------------------------------------


class IndividualDistanceMode(StrEnum):
    NONE = "none"
    TEXT = "text"
    DIMENSION = "dimension"


class DistanceLayout(StrEnum):
    ONE_LINE = "one_line"
    TWO_LINES = "two_lines"


class QuickDistanceRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    points: tuple[Point3D, ...] = Field(min_length=2)
    skipped_segment_indices: tuple[int, ...] = ()
    output_unit: LengthUnit
    drawing_units_per_millimetre: Decimal = Field(default=Decimal(1), gt=0)
    decimal_places: int = Field(default=0, ge=0, le=12)
    rounding_mode: Batch6RoundingMode = Batch6RoundingMode.HALF_UP
    individual_mode: IndividualDistanceMode = IndividualDistanceMode.NONE
    include_formula: bool = False
    include_equal_sign: bool = True
    blank_after_symbol: bool = False
    layout: DistanceLayout = DistanceLayout.ONE_LINE
    output_insertion_point: Point3D | None = None
    output_layer: str = Field(default="TEXT", min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> QuickDistanceRequest:
        max_index = len(self.points) - 2
        if any(index < 0 or index > max_index for index in self.skipped_segment_indices):
            raise ValueError("QD skipped segment index is out of range")
        if len(set(self.skipped_segment_indices)) != len(self.skipped_segment_indices):
            raise ValueError("QD skipped segment indices must be unique")
        if self.output_insertion_point is not None or self.individual_mode is not IndividualDistanceMode.NONE:
            _require_mutation_approval(self.dry_run, self.approval, "QD")
        return self


class DistanceSegment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    index: int
    start: Point3D
    end: Point3D
    drawing_length: Decimal
    output_length: Decimal
    skipped: bool


class QuickDistancePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "QD"
    legacy_symbol: str = "xiQuickDist"
    document_id: str
    segments: tuple[DistanceSegment, ...]
    total_output_length: Decimal
    formula: str | None
    rendered_text: str
    individual_mode: IndividualDistanceMode
    create_spec: TextWriteSpec | None
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def plan_quick_distance(request: QuickDistanceRequest) -> QuickDistancePlan:
    skipped = set(request.skipped_segment_indices)
    segments: list[DistanceSegment] = []
    output_values: list[Decimal] = []
    for index, (start, end) in enumerate(zip(request.points, request.points[1:], strict=False)):
        drawing_length = Decimal(str(dist((start.x, start.y, start.z), (end.x, end.y, end.z))))
        mm = drawing_length / request.drawing_units_per_millimetre
        output = mm if request.output_unit is LengthUnit.MILLIMETRE else mm / Decimal(1000)
        is_skipped = index in skipped
        segments.append(
            DistanceSegment(
                index=index,
                start=start,
                end=end,
                drawing_length=drawing_length,
                output_length=output,
                skipped=is_skipped,
            )
        )
        if not is_skipped:
            output_values.append(output)
    total = sum(output_values, Decimal(0))
    rendered_parts = [_format_decimal(value, request.decimal_places, request.rounding_mode) for value in output_values]
    formula = " + ".join(rendered_parts) if request.include_formula else None
    symbol = "= " if request.include_equal_sign else ""
    if request.blank_after_symbol and symbol:
        symbol += " "
    total_rendered = _format_decimal(total, request.decimal_places, request.rounding_mode) + request.output_unit.value
    rendered = symbol + total_rendered
    if formula:
        rendered = formula + ("\n" if request.layout is DistanceLayout.TWO_LINES else " ") + rendered
    create_spec = None
    if request.output_insertion_point is not None:
        create_spec = TextWriteSpec(
            text=rendered,
            insertion_point=request.output_insertion_point,
            layer=request.output_layer,
            text_style="Standard",
            text_height=2.5,
        )
    return QuickDistancePlan(
        document_id=request.document_id,
        segments=tuple(segments),
        total_output_length=total,
        formula=formula,
        rendered_text=rendered,
        individual_mode=request.individual_mode,
        create_spec=create_spec,
        dry_run=request.dry_run,
    )


# ---------------------------------------------------------------------------
# NUMC / TIC / TIE / TII / TIN — explicit number sequence contracts
# ---------------------------------------------------------------------------


class NumberBase(StrEnum):
    OCTAL = "octal"
    DECIMAL = "decimal"
    HEXADECIMAL = "hexadecimal"


_BASE_VALUE = {NumberBase.OCTAL: 8, NumberBase.DECIMAL: 10, NumberBase.HEXADECIMAL: 16}


class NumberSequenceSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    start: str = Field(min_length=1)
    step: int
    count: int = Field(ge=1, le=100000)
    base: NumberBase = NumberBase.DECIMAL
    prefix: str = ""
    suffix: str = ""
    suppress_leading_zero: bool = False

    @model_validator(mode="after")
    def validate_start(self) -> NumberSequenceSpec:
        try:
            int(self.start, _BASE_VALUE[self.base])
        except ValueError as exc:
            raise ValueError(f"invalid {self.base.value} start value") from exc
        return self


class GeneratedNumber(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    index: int
    numeric_value: int
    numeric_text: str
    rendered_text: str


def generate_number_sequence(spec: NumberSequenceSpec) -> tuple[GeneratedNumber, ...]:
    base = _BASE_VALUE[spec.base]
    start_value = int(spec.start, base)
    width = len(spec.start)
    generated: list[GeneratedNumber] = []
    for index in range(spec.count):
        value = start_value + spec.step * index
        if spec.base is NumberBase.HEXADECIMAL:
            numeric = format(value, "X")
        elif spec.base is NumberBase.OCTAL:
            numeric = format(value, "o")
        else:
            numeric = str(value)
        if not spec.suppress_leading_zero and value >= 0:
            numeric = numeric.zfill(width)
        generated.append(
            GeneratedNumber(
                index=index,
                numeric_value=value,
                numeric_text=numeric,
                rendered_text=f"{spec.prefix}{numeric}{spec.suffix}",
            )
        )
    return tuple(generated)


class TextAlignment(StrEnum):
    LEFT = "left"
    CENTER = "center"
    MIDDLE = "middle"
    RIGHT = "right"


class NumberPlacement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    point: Point3D
    rotation_degrees: float = 0

    @model_validator(mode="after")
    def validate_rotation(self) -> NumberPlacement:
        if not isfinite(self.rotation_degrees):
            raise ValueError("rotation must be finite")
        return self


class NumberObjectKind(StrEnum):
    TEXT = "text"
    MTEXT = "mtext"
    BLOCK_ATTRIBUTE = "block_attribute"


class NumIncRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    sequence: NumberSequenceSpec
    placements: tuple[NumberPlacement, ...] = Field(min_length=1)
    object_kind: NumberObjectKind = NumberObjectKind.TEXT
    layer: str = Field(min_length=1)
    text_style: str = Field(default="Standard", min_length=1)
    text_height: float = Field(gt=0)
    alignment: TextAlignment = TextAlignment.LEFT
    block_name: str | None = None
    attribute_tag: str | None = None
    background_mask: bool = False
    mask_offset: float | None = Field(default=None, gt=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> NumIncRequest:
        if self.sequence.count != len(self.placements):
            raise ValueError("NUMC sequence count must equal placement count")
        if self.object_kind is NumberObjectKind.BLOCK_ATTRIBUTE and (not self.block_name or not self.attribute_tag):
            raise ValueError("NUMC block_attribute requires block_name and attribute_tag")
        if self.background_mask and self.mask_offset is None:
            raise ValueError("NUMC background mask requires mask_offset")
        _require_mutation_approval(self.dry_run, self.approval, "NUMC")
        return self


class NumIncPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "NUMC"
    legacy_symbol: str = "xiNumInc"
    document_id: str
    generated: tuple[GeneratedNumber, ...]
    writes: tuple[TextWriteSpec, ...]
    object_kind: NumberObjectKind
    alignment: TextAlignment
    block_name: str | None
    attribute_tag: str | None
    background_mask: bool
    mask_offset: float | None
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def plan_num_inc(request: NumIncRequest) -> NumIncPlan:
    generated = generate_number_sequence(request.sequence)
    writes = tuple(
        TextWriteSpec(
            text=item.rendered_text,
            insertion_point=placement.point,
            layer=request.layer,
            text_style=request.text_style,
            text_height=request.text_height,
            rotation_degrees=placement.rotation_degrees,
        )
        for item, placement in zip(generated, request.placements, strict=True)
    )
    return NumIncPlan(
        document_id=request.document_id,
        generated=generated,
        writes=writes,
        object_kind=request.object_kind,
        alignment=request.alignment,
        block_name=request.block_name,
        attribute_tag=request.attribute_tag,
        background_mask=request.background_mask,
        mask_offset=request.mask_offset,
        dry_run=request.dry_run,
    )


class TargetOrder(StrEnum):
    AS_GIVEN = "as_given"
    LEFT_TO_RIGHT = "left_to_right"
    TOP_TO_BOTTOM = "top_to_bottom"


def _order_entities(entities: Sequence[TextEntitySnapshot], order: TargetOrder) -> tuple[TextEntitySnapshot, ...]:
    if order is TargetOrder.AS_GIVEN:
        return tuple(entities)
    if order is TargetOrder.LEFT_TO_RIGHT:
        return tuple(sorted(entities, key=lambda e: (e.insertion_point.x, -e.insertion_point.y, e.handle)))
    return tuple(sorted(entities, key=lambda e: (-e.insertion_point.y, e.insertion_point.x, e.handle)))


class ExistingNumberPolicy(StrEnum):
    REPLACE = "replace"
    ADD = "add"


class AutoNumberingRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    sequence: NumberSequenceSpec
    order: TargetOrder = TargetOrder.AS_GIVEN
    number_policy: ExistingNumberPolicy = ExistingNumberPolicy.REPLACE
    numeric_token_policy: LevelNumberPolicy = LevelNumberPolicy.LAST
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> AutoNumberingRequest:
        _unique(self.target_handles, "target_handles")
        if self.sequence.count != len(self.target_handles):
            raise ValueError("TIC sequence count must equal target count")
        _require_mutation_approval(self.dry_run, self.approval, "TIC")
        return self


class TextNumberingPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    ordered_handles: tuple[str, ...]
    changes: tuple[TextChange, ...]
    create_specs: tuple[TextWriteSpec, ...]
    dry_run: bool
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def plan_auto_numbering(
    request: AutoNumberingRequest,
    entities: Sequence[TextEntitySnapshot],
) -> TextNumberingPlan:
    selected = _order_entities(_select_mutable_texts(request.target_handles, entities), request.order)
    generated = generate_number_sequence(request.sequence)
    changes: list[TextChange] = []
    for entity, number in zip(selected, generated, strict=True):
        matches = _numeric_matches(entity.text)
        if not matches:
            if request.number_policy is ExistingNumberPolicy.ADD:
                replacement = entity.text + number.rendered_text
            else:
                raise ValueError(f"TIC target has no numeric token: {entity.handle}")
        else:
            match = matches[0] if request.numeric_token_policy is LevelNumberPolicy.FIRST else matches[-1]
            if request.number_policy is ExistingNumberPolicy.ADD:
                original = int(match.group("num"), 10)
                value = original + number.numeric_value
                numeric = str(value)
                replacement = (
                    entity.text[: match.start()]
                    + request.sequence.prefix
                    + numeric
                    + request.sequence.suffix
                    + entity.text[match.end() :]
                )
            else:
                replacement = entity.text[: match.start()] + number.rendered_text + entity.text[match.end() :]
        changes.append(TextChange(handle=entity.handle, expected_text=entity.text, replacement_text=replacement))
    return TextNumberingPlan(
        command_alias="TIC",
        legacy_symbol="xiAutoNumbering",
        document_id=request.document_id,
        ordered_handles=tuple(entity.handle for entity in selected),
        changes=tuple(changes),
        create_specs=(),
        dry_run=request.dry_run,
    )


class AffixPlacement(StrEnum):
    FRONT = "front"
    BACK = "back"


class PickNumberIncrementRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handles: tuple[str, ...] = Field(min_length=1)
    sequence: NumberSequenceSpec
    placement: AffixPlacement
    separator: str = " "
    copy_offset: Point3D = Point3D(x=0, y=0, z=0)
    order: TargetOrder = TargetOrder.AS_GIVEN
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> PickNumberIncrementRequest:
        _unique(self.source_handles, "source_handles")
        if self.sequence.count != len(self.source_handles):
            raise ValueError("TIE sequence count must equal source count")
        _require_mutation_approval(self.dry_run, self.approval, "TIE")
        return self


def plan_pick_number_increment(
    request: PickNumberIncrementRequest,
    entities: Sequence[TextEntitySnapshot],
) -> TextNumberingPlan:
    selected = _order_entities(_select_mutable_texts(request.source_handles, entities), request.order)
    generated = generate_number_sequence(request.sequence)
    creates: list[TextWriteSpec] = []
    for entity, number in zip(selected, generated, strict=True):
        text = (
            f"{number.rendered_text}{request.separator}{entity.text}"
            if request.placement is AffixPlacement.FRONT
            else f"{entity.text}{request.separator}{number.rendered_text}"
        )
        creates.append(
            TextWriteSpec(
                text=text,
                insertion_point=Point3D(
                    x=entity.insertion_point.x + request.copy_offset.x,
                    y=entity.insertion_point.y + request.copy_offset.y,
                    z=entity.insertion_point.z + request.copy_offset.z,
                ),
                layer=entity.layer,
                text_style=entity.text_style,
                text_height=entity.text_height,
                rotation_degrees=entity.rotation_degrees,
            )
        )
    return TextNumberingPlan(
        command_alias="TIE",
        legacy_symbol="xiPickNumInc",
        document_id=request.document_id,
        ordered_handles=tuple(entity.handle for entity in selected),
        changes=(),
        create_specs=tuple(creates),
        dry_run=request.dry_run,
    )


class TextIncrementInputRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    sequence: NumberSequenceSpec
    placements: tuple[NumberPlacement, ...] = Field(min_length=1)
    layer: str = Field(min_length=1)
    text_style: str = Field(default="Standard", min_length=1)
    text_height: float = Field(gt=0)
    alignment: TextAlignment = TextAlignment.LEFT
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TextIncrementInputRequest:
        if self.sequence.count != len(self.placements):
            raise ValueError("TII sequence count must equal placement count")
        _require_mutation_approval(self.dry_run, self.approval, "TII")
        return self


def plan_text_increment_input(request: TextIncrementInputRequest) -> TextNumberingPlan:
    generated = generate_number_sequence(request.sequence)
    creates = tuple(
        TextWriteSpec(
            text=number.rendered_text,
            insertion_point=placement.point,
            layer=request.layer,
            text_style=request.text_style,
            text_height=request.text_height,
            rotation_degrees=placement.rotation_degrees,
        )
        for number, placement in zip(generated, request.placements, strict=True)
    )
    return TextNumberingPlan(
        command_alias="TII",
        legacy_symbol="xiTextIncInput",
        document_id=request.document_id,
        ordered_handles=(),
        changes=(),
        create_specs=creates,
        dry_run=request.dry_run,
    )


class EmbeddedNumberIncrementRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    sequence: NumberSequenceSpec
    token_policy: LevelNumberPolicy = LevelNumberPolicy.LAST
    order: TargetOrder = TargetOrder.AS_GIVEN
    allowed_kinds: tuple[TextEntityKind, ...] = (
        TextEntityKind.TEXT,
        TextEntityKind.MTEXT,
        TextEntityKind.ATTRIB,
        TextEntityKind.MLEADER,
    )
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> EmbeddedNumberIncrementRequest:
        _unique(self.target_handles, "target_handles")
        if self.sequence.count != len(self.target_handles):
            raise ValueError("TIN sequence count must equal target count")
        if not self.allowed_kinds:
            raise ValueError("TIN allowed_kinds must not be empty")
        _require_mutation_approval(self.dry_run, self.approval, "TIN")
        return self


def plan_embedded_number_increment(
    request: EmbeddedNumberIncrementRequest,
    entities: Sequence[TextEntitySnapshot],
) -> TextNumberingPlan:
    selected = _order_entities(_select_mutable_texts(request.target_handles, entities), request.order)
    generated = generate_number_sequence(request.sequence)
    changes: list[TextChange] = []
    for entity, number in zip(selected, generated, strict=True):
        if entity.kind not in request.allowed_kinds:
            raise ValueError(f"TIN target kind is not allowed: {entity.handle}")
        matches = _numeric_matches(entity.text)
        if not matches:
            raise ValueError(f"TIN target has no numeric token: {entity.handle}")
        match = matches[0] if request.token_policy is LevelNumberPolicy.FIRST else matches[-1]
        replacement = entity.text[: match.start()] + number.rendered_text + entity.text[match.end() :]
        changes.append(TextChange(handle=entity.handle, expected_text=entity.text, replacement_text=replacement))
    return TextNumberingPlan(
        command_alias="TIN",
        legacy_symbol="xiTextInEttsInc",
        document_id=request.document_id,
        ordered_handles=tuple(entity.handle for entity in selected),
        changes=tuple(changes),
        create_specs=(),
        dry_run=request.dry_run,
    )


# ---------------------------------------------------------------------------
# MCP read-only planner registration
# ---------------------------------------------------------------------------


def register_headless_core_batch6_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(
        title="xiCAD Headless Core Batch 6 Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @mcp.tool(name="xicad_plan_m2", annotations=read_only)
    def mcp_plan_m2(request: PyeongToSquareMetreRequest) -> PyeongToSquareMetrePlan:
        return plan_pyeong_to_square_metres(request)

    @mcp.tool(name="xicad_plan_ina", annotations=read_only)
    def mcp_plan_ina(request: SymbolAggregateRequest) -> SymbolAggregatePlan:
        return plan_symbol_aggregate(request, command_alias="INA")

    @mcp.tool(name="xicad_plan_spn", annotations=read_only)
    def mcp_plan_spn(request: SymbolAggregateRequest) -> SymbolAggregatePlan:
        return plan_symbol_aggregate(request, command_alias="SPN")

    @mcp.tool(name="xicad_plan_lis", annotations=read_only)
    def mcp_plan_lis(request: LineSumRequest, curves: tuple[CurveLengthSnapshot, ...]) -> LineSumPlan:
        return plan_line_sum(request, curves)

    @mcp.tool(name="xicad_plan_lma", annotations=read_only)
    def mcp_plan_lma(request: LevelMoveAddRequest, entities: tuple[TextEntitySnapshot, ...]) -> LevelTransformPlan:
        return plan_level_move_add(request, entities)

    @mcp.tool(name="xicad_plan_lna", annotations=read_only)
    def mcp_plan_lna(request: LevelNumberAddRequest, entities: tuple[TextEntitySnapshot, ...]) -> LevelTransformPlan:
        return plan_level_number_add(request, entities)

    @mcp.tool(name="xicad_plan_qd", annotations=read_only)
    def mcp_plan_qd(request: QuickDistanceRequest) -> QuickDistancePlan:
        return plan_quick_distance(request)

    @mcp.tool(name="xicad_plan_numc", annotations=read_only)
    def mcp_plan_numc(request: NumIncRequest) -> NumIncPlan:
        return plan_num_inc(request)

    @mcp.tool(name="xicad_plan_tic", annotations=read_only)
    def mcp_plan_tic(request: AutoNumberingRequest, entities: tuple[TextEntitySnapshot, ...]) -> TextNumberingPlan:
        return plan_auto_numbering(request, entities)

    @mcp.tool(name="xicad_plan_tie", annotations=read_only)
    def mcp_plan_tie(
        request: PickNumberIncrementRequest, entities: tuple[TextEntitySnapshot, ...]
    ) -> TextNumberingPlan:
        return plan_pick_number_increment(request, entities)

    @mcp.tool(name="xicad_plan_tii", annotations=read_only)
    def mcp_plan_tii(request: TextIncrementInputRequest) -> TextNumberingPlan:
        return plan_text_increment_input(request)

    @mcp.tool(name="xicad_plan_tin", annotations=read_only)
    def mcp_plan_tin(
        request: EmbeddedNumberIncrementRequest, entities: tuple[TextEntitySnapshot, ...]
    ) -> TextNumberingPlan:
        return plan_embedded_number_increment(request, entities)
