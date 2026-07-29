from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from enum import StrEnum
from math import isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


class TextEntityKind(StrEnum):
    TEXT = "text"
    MTEXT = "mtext"
    ATTRIB = "attrib"
    ATTDEF = "attdef"
    DIMENSION = "dimension"
    MLEADER = "mleader"
    TABLE_CELL = "table_cell"


class DrawingSpace(StrEnum):
    MODEL = "model"
    PAPER = "paper"


class TextEntitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    text: str
    kind: TextEntityKind
    layer: str = Field(min_length=1)
    text_style: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    insertion_point: Point3D = Point3D(x=0, y=0, z=0)
    rotation_degrees: float = 0.0
    space: DrawingSpace = DrawingSpace.MODEL
    block_name: str | None = None
    locked_layer: bool = False
    is_xref: bool = False

    @model_validator(mode="after")
    def validate_rotation(self) -> TextEntitySnapshot:
        if not isfinite(self.rotation_degrees):
            raise ValueError("rotation_degrees must be finite")
        return self


class TextChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_text: str
    replacement_text: str


class TextHeightChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    expected_height: float
    replacement_height: float = Field(gt=0)


class TextWriteSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str
    insertion_point: Point3D
    layer: str = Field(min_length=1)
    text_style: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    rotation_degrees: float = 0.0

    @model_validator(mode="after")
    def validate_rotation(self) -> TextWriteSpec:
        if not isfinite(self.rotation_degrees):
            raise ValueError("rotation_degrees must be finite")
        return self


def _unique_handles(values: Sequence[str], field_name: str) -> None:
    normalized = [value.casefold() for value in values]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} must be unique")


def _snapshot_map(entities: Sequence[TextEntitySnapshot]) -> dict[str, TextEntitySnapshot]:
    result: dict[str, TextEntitySnapshot] = {}
    for entity in entities:
        key = entity.handle.casefold()
        if key in result:
            raise ValueError(f"duplicate snapshot handle: {entity.handle}")
        result[key] = entity
    return result


def _selected_entities(
    handles: Sequence[str], entities: Sequence[TextEntitySnapshot]
) -> tuple[TextEntitySnapshot, ...]:
    by_handle = _snapshot_map(entities)
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


_NUMBER_TOKEN_RE = re.compile(
    r"(?<![\d.])(?P<open>\()?(?P<sign>[+-]?)(?P<int>(?:\d{1,3}(?:,\d{3})+|\d+))(?P<frac>\.\d+)?(?P<close>\))?(?![\d.])"
)


def _insert_commas_in_text(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        integer = match.group("int").replace(",", "")
        grouped = f"{int(integer):,}"
        return f"{match.group('open') or ''}{match.group('sign')}{grouped}{match.group('frac') or ''}{match.group('close') or ''}"

    return _NUMBER_TOKEN_RE.sub(replace, text)


def _remove_commas_in_text(text: str) -> str:
    return re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", text)


class NumericFormatMode(StrEnum):
    INSERT_COMMAS = "insert_commas"
    REMOVE_COMMAS = "remove_commas"


class NumericTextFormatRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    mode: NumericFormatMode
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> NumericTextFormatRequest:
        _unique_handles(self.target_handles, "target_handles")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("COI/COR execution requires explicit approval")
        return self


class NumericTextFormatPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    changes: tuple[TextChange, ...]
    unchanged_handles: tuple[str, ...]
    destructive: bool = True
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def plan_numeric_text_format(
    request: NumericTextFormatRequest,
    entities: Sequence[TextEntitySnapshot],
) -> NumericTextFormatPlan:
    selected = _selected_entities(request.target_handles, entities)
    transform = _insert_commas_in_text if request.mode is NumericFormatMode.INSERT_COMMAS else _remove_commas_in_text
    changes: list[TextChange] = []
    unchanged: list[str] = []
    for entity in selected:
        replacement = transform(entity.text)
        if replacement == entity.text:
            unchanged.append(entity.handle)
        else:
            changes.append(TextChange(handle=entity.handle, expected_text=entity.text, replacement_text=replacement))
    alias, symbol = ("COI", "xiCommaIns") if request.mode is NumericFormatMode.INSERT_COMMAS else ("COR", "xiCommaRem")
    return NumericTextFormatPlan(
        command_alias=alias,
        legacy_symbol=symbol,
        document_id=request.document_id,
        changes=tuple(changes),
        unchanged_handles=tuple(unchanged),
        dry_run=request.dry_run,
    )


class GroupNumericOperation(StrEnum):
    DIVIDE_GROUP_SUMS = "divide_group_sums"
    SUBTRACT_GROUP_SUMS = "subtract_group_sums"
    DISTRIBUTION_CHECK = "distribution_check"


class DistributionMode(StrEnum):
    GROUP_SUM_PRODUCT = "group_sum_product"
    PAIRWISE_PRODUCT_SUM = "pairwise_product_sum"


class GroupNumericRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    operation: GroupNumericOperation
    first_group: tuple[Decimal, ...] = Field(min_length=1)
    second_group: tuple[Decimal, ...] = Field(min_length=1)
    distribution_mode: DistributionMode | None = None
    decimal_places: int | None = Field(default=None, ge=0, le=12)

    @model_validator(mode="after")
    def validate_request(self) -> GroupNumericRequest:
        if self.operation is GroupNumericOperation.DISTRIBUTION_CHECK:
            if self.distribution_mode is None:
                raise ValueError("NP requires an explicit distribution_mode")
            if self.distribution_mode is DistributionMode.PAIRWISE_PRODUCT_SUM and len(self.first_group) != len(
                self.second_group
            ):
                raise ValueError("pairwise NP groups must have equal length")
        elif self.distribution_mode is not None:
            raise ValueError("distribution_mode is only valid for NP")
        return self


class GroupNumericPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    operation: GroupNumericOperation
    first_sum: Decimal
    second_sum: Decimal
    exact_result: Decimal
    result: Decimal
    decimal_places: int | None
    distribution_mode: DistributionMode | None
    cad_required: bool = False
    dialog_required: bool = False
    deterministic: bool = True
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = True


def _quantize(value: Decimal, places: int | None, rounding: str = ROUND_HALF_UP) -> Decimal:
    if places is None:
        return value
    return value.quantize(Decimal(1).scaleb(-places), rounding=rounding)


def plan_group_numeric_operation(request: GroupNumericRequest) -> GroupNumericPlan:
    first_sum = sum(request.first_group, Decimal(0))
    second_sum = sum(request.second_group, Decimal(0))
    if request.operation is GroupNumericOperation.DIVIDE_GROUP_SUMS:
        if second_sum == 0:
            raise ValueError("ND denominator group sum must not be zero")
        exact = first_sum / second_sum
        alias, symbol = "ND", "xiNumDivide"
    elif request.operation is GroupNumericOperation.SUBTRACT_GROUP_SUMS:
        exact = first_sum - second_sum
        alias, symbol = "NS", "xiNumSubtract"
    else:
        alias, symbol = "NP", "xiNumBunyangPro"
        if request.distribution_mode is DistributionMode.GROUP_SUM_PRODUCT:
            exact = first_sum * second_sum
        else:
            exact = sum(
                (a * b for a, b in zip(request.first_group, request.second_group, strict=True)),
                Decimal(0),
            )
    return GroupNumericPlan(
        command_alias=alias,
        legacy_symbol=symbol,
        operation=request.operation,
        first_sum=first_sum,
        second_sum=second_sum,
        exact_result=exact,
        result=_quantize(exact, request.decimal_places),
        decimal_places=request.decimal_places,
        distribution_mode=request.distribution_mode,
    )


class BulkNumberOperation(StrEnum):
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"


class DecimalPlacesPolicy(StrEnum):
    PRESERVE_INPUT = "preserve_input"
    FIXED = "fixed"


class RoundingMode(StrEnum):
    FLOOR = "floor"
    HALF_UP = "half_up"
    CEILING = "ceiling"


_ROUNDING_MAP = {
    RoundingMode.FLOOR: ROUND_FLOOR,
    RoundingMode.HALF_UP: ROUND_HALF_UP,
    RoundingMode.CEILING: ROUND_CEILING,
}


class BulkNumberCalculationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    operation: BulkNumberOperation
    operand: Decimal
    decimal_places_policy: DecimalPlacesPolicy
    decimal_places: int | None = Field(default=None, ge=0, le=12)
    rounding_mode: RoundingMode = RoundingMode.HALF_UP
    thousands_separator: bool = False
    recognize_parenthesized_negative: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> BulkNumberCalculationRequest:
        _unique_handles(self.target_handles, "target_handles")
        if self.operation is BulkNumberOperation.DIVIDE and self.operand == 0:
            raise ValueError("NUC divisor must not be zero")
        if self.decimal_places_policy is DecimalPlacesPolicy.FIXED and self.decimal_places is None:
            raise ValueError("fixed decimal policy requires decimal_places")
        if self.decimal_places_policy is DecimalPlacesPolicy.PRESERVE_INPUT and self.decimal_places is not None:
            raise ValueError("preserve_input decimal policy must not set decimal_places")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("NUC execution requires explicit approval")
        return self


class BulkNumberCalculationPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "NUC"
    legacy_symbol: str = "xiNumberCalulate"
    document_id: str
    changes: tuple[TextChange, ...]
    unchanged_handles: tuple[str, ...]
    operation: BulkNumberOperation
    operand: Decimal
    destructive: bool = True
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def _apply_bulk_operation(value: Decimal, operation: BulkNumberOperation, operand: Decimal) -> Decimal:
    if operation is BulkNumberOperation.ADD:
        return value + operand
    if operation is BulkNumberOperation.SUBTRACT:
        return value - operand
    if operation is BulkNumberOperation.MULTIPLY:
        return value * operand
    if operand == 0:
        raise ValueError("division by zero")
    return value / operand


def _format_decimal(value: Decimal, places: int, rounding_mode: RoundingMode, commas: bool) -> str:
    quantized = _quantize(value, places, _ROUNDING_MAP[rounding_mode])
    text = f"{quantized:.{places}f}"
    if commas:
        sign = ""
        if text.startswith("-"):
            sign, text = "-", text[1:]
        integer, dot, fraction = text.partition(".")
        text = f"{int(integer):,}{dot}{fraction}"
        text = sign + text
    return text


def _transform_numbers_in_text(text: str, request: BulkNumberCalculationRequest) -> str:
    def replace(match: re.Match[str]) -> str:
        open_paren = match.group("open") or ""
        close_paren = match.group("close") or ""
        parenthesized = bool(open_paren and close_paren)
        raw = f"{match.group('sign')}{match.group('int').replace(',', '')}{match.group('frac') or ''}"
        value = Decimal(raw)
        if parenthesized and request.recognize_parenthesized_negative and value >= 0:
            value = -value
        result = _apply_bulk_operation(value, request.operation, request.operand)
        input_places = len((match.group("frac") or "").lstrip("."))
        places = request.decimal_places if request.decimal_places_policy is DecimalPlacesPolicy.FIXED else input_places
        rendered = _format_decimal(result, places, request.rounding_mode, request.thousands_separator)
        if parenthesized and request.recognize_parenthesized_negative and result < 0:
            return f"({rendered.lstrip('-')})"
        return rendered

    return _NUMBER_TOKEN_RE.sub(replace, text)


def plan_bulk_number_calculation(
    request: BulkNumberCalculationRequest,
    entities: Sequence[TextEntitySnapshot],
) -> BulkNumberCalculationPlan:
    selected = _selected_entities(request.target_handles, entities)
    changes: list[TextChange] = []
    unchanged: list[str] = []
    for entity in selected:
        replacement = _transform_numbers_in_text(entity.text, request)
        if replacement == entity.text:
            unchanged.append(entity.handle)
        else:
            changes.append(TextChange(handle=entity.handle, expected_text=entity.text, replacement_text=replacement))
    return BulkNumberCalculationPlan(
        document_id=request.document_id,
        changes=tuple(changes),
        unchanged_handles=tuple(unchanged),
        operation=request.operation,
        operand=request.operand,
        dry_run=request.dry_run,
    )


class PyeongOutputMode(StrEnum):
    REPLACE_SOURCE = "replace_source"
    UPDATE_TARGET = "update_target"
    CREATE_NEW = "create_new"


class PyeongInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    square_metres: Decimal


class SquareMetreToPyeongRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    inputs: tuple[PyeongInput, ...] = Field(min_length=1)
    output_mode: PyeongOutputMode
    target_handles: tuple[str, ...] = ()
    insertion_points: tuple[Point3D, ...] = ()
    decimal_places: int = Field(ge=0, le=12)
    rounding_mode: RoundingMode
    thousands_separator: bool
    unit_text: str
    include_parentheses: bool
    output_layer: str = Field(min_length=1)
    output_text_style: str = Field(min_length=1)
    output_text_height: float = Field(gt=0)
    output_rotation_degrees: float = 0.0
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> SquareMetreToPyeongRequest:
        _unique_handles([item.source_handle for item in self.inputs], "source handles")
        if self.output_mode is PyeongOutputMode.UPDATE_TARGET:
            if len(self.target_handles) != len(self.inputs):
                raise ValueError("PY update_target requires one target handle per input")
            _unique_handles(self.target_handles, "target_handles")
        elif self.target_handles:
            raise ValueError("target_handles are only valid for update_target")
        if self.output_mode is PyeongOutputMode.CREATE_NEW:
            if len(self.insertion_points) != len(self.inputs):
                raise ValueError("PY create_new requires one insertion point per input")
        elif self.insertion_points:
            raise ValueError("insertion_points are only valid for create_new")
        if not isfinite(self.output_rotation_degrees):
            raise ValueError("output_rotation_degrees must be finite")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("PY execution requires explicit approval")
        return self


class PyeongOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    square_metres: Decimal
    exact_pyeong: Decimal
    pyeong: Decimal
    rendered_text: str
    target_handle: str | None = None
    create_spec: TextWriteSpec | None = None


class SquareMetreToPyeongPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "PY"
    legacy_symbol: str = "xiPy"
    document_id: str
    conversion_factor: Decimal = Decimal("0.3025")
    output_mode: PyeongOutputMode
    outputs: tuple[PyeongOutput, ...]
    destructive: bool
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def plan_square_metre_to_pyeong(request: SquareMetreToPyeongRequest) -> SquareMetreToPyeongPlan:
    outputs: list[PyeongOutput] = []
    for index, item in enumerate(request.inputs):
        exact = item.square_metres * Decimal("0.3025")
        rounded = _quantize(exact, request.decimal_places, _ROUNDING_MAP[request.rounding_mode])
        rendered = _format_decimal(rounded, request.decimal_places, request.rounding_mode, request.thousands_separator)
        rendered = f"{rendered}{request.unit_text}"
        if request.include_parentheses:
            rendered = f"({rendered})"
        target: str | None = None
        create_spec: TextWriteSpec | None = None
        if request.output_mode is PyeongOutputMode.REPLACE_SOURCE:
            target = item.source_handle
        elif request.output_mode is PyeongOutputMode.UPDATE_TARGET:
            target = request.target_handles[index]
        else:
            create_spec = TextWriteSpec(
                text=rendered,
                insertion_point=request.insertion_points[index],
                layer=request.output_layer,
                text_style=request.output_text_style,
                text_height=request.output_text_height,
                rotation_degrees=request.output_rotation_degrees,
            )
        outputs.append(
            PyeongOutput(
                source_handle=item.source_handle,
                square_metres=item.square_metres,
                exact_pyeong=exact,
                pyeong=rounded,
                rendered_text=rendered,
                target_handle=target,
                create_spec=create_spec,
            )
        )
    return SquareMetreToPyeongPlan(
        document_id=request.document_id,
        output_mode=request.output_mode,
        outputs=tuple(outputs),
        destructive=request.output_mode is not PyeongOutputMode.CREATE_NEW,
        dry_run=request.dry_run,
    )


class TextMatchMode(StrEnum):
    WHOLE = "whole"
    SUBSTRING = "substring"


class FindReplaceRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    old: str = Field(min_length=1)
    new: str


class FindReplaceRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    rules: tuple[FindReplaceRule, ...] = Field(min_length=1)
    match_mode: TextMatchMode
    case_sensitive: bool
    ignore_spaces: bool
    search_only: bool
    allowed_kinds: tuple[TextEntityKind, ...] = Field(min_length=1)
    allowed_layers: tuple[str, ...] = ()
    allowed_heights: tuple[float, ...] = ()
    allowed_block_names: tuple[str, ...] = ()
    allowed_spaces: tuple[DrawingSpace, ...] = (DrawingSpace.MODEL, DrawingSpace.PAPER)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> FindReplaceRequest:
        _unique_handles(self.target_handles, "target_handles")
        if self.ignore_spaces and self.match_mode is TextMatchMode.SUBSTRING:
            raise ValueError("ignore_spaces is only deterministic with whole-string matching")
        keys = [rule.old if self.case_sensitive else rule.old.casefold() for rule in self.rules]
        if len(keys) != len(set(keys)):
            raise ValueError("find/replace rule keys must be unique")
        if any(height <= 0 or not isfinite(height) for height in self.allowed_heights):
            raise ValueError("allowed_heights must contain positive finite values")
        if not self.dry_run and not self.search_only and not self.approval.approved:
            raise ValueError("FAR replacement requires explicit approval")
        return self


class MatchRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str
    original_text: str
    result_text: str
    changed: bool


class FindReplacePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "FAR"
    legacy_symbol: str = "xiFindReplace"
    document_id: str
    records: tuple[MatchRecord, ...]
    skipped_handles: tuple[str, ...]
    search_only: bool
    destructive: bool
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def _whole_key(value: str, *, case_sensitive: bool, ignore_spaces: bool) -> str:
    if ignore_spaces:
        value = "".join(value.split())
    return value if case_sensitive else value.casefold()


def _replace_rule(text: str, rule: FindReplaceRule, request: FindReplaceRequest) -> tuple[str, bool]:
    if request.match_mode is TextMatchMode.WHOLE:
        if _whole_key(text, case_sensitive=request.case_sensitive, ignore_spaces=request.ignore_spaces) == _whole_key(
            rule.old, case_sensitive=request.case_sensitive, ignore_spaces=request.ignore_spaces
        ):
            return rule.new, True
        return text, False
    flags = 0 if request.case_sensitive else re.IGNORECASE
    replaced, count = re.subn(re.escape(rule.old), lambda _match: rule.new, text, flags=flags)
    return replaced, count > 0


def plan_find_replace(request: FindReplaceRequest, entities: Sequence[TextEntitySnapshot]) -> FindReplacePlan:
    selected = _selected_entities(request.target_handles, entities)
    allowed_layers = {value.casefold() for value in request.allowed_layers}
    allowed_blocks = {value.casefold() for value in request.allowed_block_names}
    allowed_heights = set(request.allowed_heights)
    records: list[MatchRecord] = []
    skipped: list[str] = []
    for entity in selected:
        if entity.kind not in request.allowed_kinds or entity.space not in request.allowed_spaces:
            skipped.append(entity.handle)
            continue
        if allowed_layers and entity.layer.casefold() not in allowed_layers:
            skipped.append(entity.handle)
            continue
        if allowed_blocks and (entity.block_name or "").casefold() not in allowed_blocks:
            skipped.append(entity.handle)
            continue
        if allowed_heights and entity.text_height not in allowed_heights:
            skipped.append(entity.handle)
            continue
        result = entity.text
        matched = False
        for rule in request.rules:
            result, did_match = _replace_rule(result, rule, request)
            matched = matched or did_match
        if matched:
            records.append(
                MatchRecord(
                    handle=entity.handle,
                    original_text=entity.text,
                    result_text=entity.text if request.search_only else result,
                    changed=(not request.search_only and result != entity.text),
                )
            )
    return FindReplacePlan(
        document_id=request.document_id,
        records=tuple(records),
        skipped_handles=tuple(skipped),
        search_only=request.search_only,
        destructive=not request.search_only,
        dry_run=request.dry_run,
    )


class TextAffixRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    prefix: str
    suffix: str
    trim_existing: bool = False
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TextAffixRequest:
        _unique_handles(self.target_handles, "target_handles")
        if not self.prefix and not self.suffix:
            raise ValueError("TAP requires a non-empty prefix or suffix")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("TAP execution requires explicit approval")
        return self


class TextAffixPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "TAP"
    legacy_symbol: str = "xiTextAp"
    document_id: str
    changes: tuple[TextChange, ...]
    destructive: bool = True
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def plan_text_affix(request: TextAffixRequest, entities: Sequence[TextEntitySnapshot]) -> TextAffixPlan:
    selected = _selected_entities(request.target_handles, entities)
    changes = []
    for entity in selected:
        base = entity.text.strip() if request.trim_existing else entity.text
        changes.append(
            TextChange(
                handle=entity.handle,
                expected_text=entity.text,
                replacement_text=f"{request.prefix}{base}{request.suffix}",
            )
        )
    return TextAffixPlan(document_id=request.document_id, changes=tuple(changes), dry_run=request.dry_run)


class SplitMode(StrEnum):
    INDEX = "index"
    DELIMITER = "delimiter"


class DelimiterOccurrence(StrEnum):
    FIRST = "first"
    LAST = "last"


class TextDivideRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    source_handle: str = Field(min_length=1)
    split_mode: SplitMode
    split_index: int | None = Field(default=None, ge=1)
    delimiter: str | None = None
    delimiter_occurrence: DelimiterOccurrence | None = None
    preserve_original: bool
    trim_original_part: bool
    trim_new_part: bool
    between_text: str
    new_insertion_point: Point3D
    new_line_gap_multiplier: float = Field(gt=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TextDivideRequest:
        if self.split_mode is SplitMode.INDEX:
            if self.split_index is None or self.delimiter is not None or self.delimiter_occurrence is not None:
                raise ValueError("TD index mode requires only split_index")
        else:
            if not self.delimiter or self.delimiter_occurrence is None or self.split_index is not None:
                raise ValueError("TD delimiter mode requires delimiter and delimiter_occurrence")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("TD execution requires explicit approval")
        return self


class TextDividePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "TD"
    legacy_symbol: str = "xiTextDivide"
    document_id: str
    source_handle: str
    source_change: TextChange | None
    create_spec: TextWriteSpec
    preserve_original: bool
    new_line_gap_multiplier: float
    destructive: bool
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def plan_text_divide(request: TextDivideRequest, source: TextEntitySnapshot) -> TextDividePlan:
    if source.handle.casefold() != request.source_handle.casefold():
        raise ValueError("TD source handle mismatch")
    if source.is_xref or source.locked_layer:
        raise ValueError("TD source is not mutable")
    text = source.text
    if request.split_mode is SplitMode.INDEX:
        assert request.split_index is not None
        if request.split_index >= len(text):
            raise ValueError("TD split_index must be inside the source string")
        left, right = text[: request.split_index], text[request.split_index :]
    else:
        assert request.delimiter is not None and request.delimiter_occurrence is not None
        position = (
            text.find(request.delimiter)
            if request.delimiter_occurrence is DelimiterOccurrence.FIRST
            else text.rfind(request.delimiter)
        )
        if position < 0:
            raise ValueError("TD delimiter not found")
        left = text[:position]
        right = text[position + len(request.delimiter) :]
    if request.trim_original_part:
        left = left.strip()
    if request.trim_new_part:
        right = right.strip()
    if not left or not right:
        raise ValueError("TD split must produce two non-empty strings")
    source_change = None
    if not request.preserve_original:
        source_change = TextChange(handle=source.handle, expected_text=source.text, replacement_text=left)
    create_text = f"{request.between_text}{right}" if request.between_text else right
    create_spec = TextWriteSpec(
        text=create_text,
        insertion_point=request.new_insertion_point,
        layer=source.layer,
        text_style=source.text_style,
        text_height=source.text_height,
        rotation_degrees=source.rotation_degrees,
    )
    return TextDividePlan(
        document_id=request.document_id,
        source_handle=source.handle,
        source_change=source_change,
        create_spec=create_spec,
        preserve_original=request.preserve_original,
        new_line_gap_multiplier=request.new_line_gap_multiplier,
        destructive=not request.preserve_original,
        dry_run=request.dry_run,
    )


class MergeOrder(StrEnum):
    AS_GIVEN = "as_given"
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"
    TOP_TO_BOTTOM = "top_to_bottom"
    BOTTOM_TO_TOP = "bottom_to_top"


class MergeSourcePolicy(StrEnum):
    PRESERVE_ALL = "preserve_all"
    REPLACE_FIRST_ERASE_REST = "replace_first_erase_rest"
    CREATE_NEW_ERASE_ALL = "create_new_erase_all"


class TextMergeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    ordered_handles: tuple[str, ...] = Field(min_length=2)
    order: MergeOrder
    separator: str
    source_policy: MergeSourcePolicy
    output_insertion_point: Point3D | None = None
    output_layer: str | None = None
    output_text_style: str | None = None
    output_text_height: float | None = Field(default=None, gt=0)
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TextMergeRequest:
        _unique_handles(self.ordered_handles, "ordered_handles")
        if self.source_policy is MergeSourcePolicy.CREATE_NEW_ERASE_ALL and self.output_insertion_point is None:
            raise ValueError("TM create_new_erase_all requires output_insertion_point")
        if not self.dry_run and self.source_policy is not MergeSourcePolicy.PRESERVE_ALL and not self.approval.approved:
            raise ValueError("TM destructive execution requires explicit approval")
        return self


class TextMergePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "TM"
    legacy_symbol: str = "xiTextMerge"
    document_id: str
    ordered_handles: tuple[str, ...]
    merged_text: str
    source_change: TextChange | None
    create_spec: TextWriteSpec | None
    erase_handles: tuple[str, ...]
    destructive: bool
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def _sort_merge_entities(entities: Sequence[TextEntitySnapshot], order: MergeOrder) -> tuple[TextEntitySnapshot, ...]:
    if order is MergeOrder.AS_GIVEN:
        return tuple(entities)
    if order is MergeOrder.LEFT_TO_RIGHT:
        return tuple(sorted(entities, key=lambda item: (item.insertion_point.x, -item.insertion_point.y, item.handle)))
    if order is MergeOrder.RIGHT_TO_LEFT:
        return tuple(sorted(entities, key=lambda item: (-item.insertion_point.x, -item.insertion_point.y, item.handle)))
    if order is MergeOrder.TOP_TO_BOTTOM:
        return tuple(sorted(entities, key=lambda item: (-item.insertion_point.y, item.insertion_point.x, item.handle)))
    return tuple(sorted(entities, key=lambda item: (item.insertion_point.y, item.insertion_point.x, item.handle)))


def plan_text_merge(request: TextMergeRequest, entities: Sequence[TextEntitySnapshot]) -> TextMergePlan:
    selected = _selected_entities(request.ordered_handles, entities)
    ordered = _sort_merge_entities(selected, request.order)
    merged = request.separator.join(item.text for item in ordered)
    first = ordered[0]
    source_change: TextChange | None = None
    create_spec: TextWriteSpec | None = None
    erase: tuple[str, ...] = ()
    if request.source_policy is MergeSourcePolicy.REPLACE_FIRST_ERASE_REST:
        source_change = TextChange(handle=first.handle, expected_text=first.text, replacement_text=merged)
        erase = tuple(item.handle for item in ordered[1:])
    elif request.source_policy is MergeSourcePolicy.CREATE_NEW_ERASE_ALL:
        create_spec = TextWriteSpec(
            text=merged,
            insertion_point=request.output_insertion_point or first.insertion_point,
            layer=request.output_layer or first.layer,
            text_style=request.output_text_style or first.text_style,
            text_height=request.output_text_height or first.text_height,
            rotation_degrees=first.rotation_degrees,
        )
        erase = tuple(item.handle for item in ordered)
    else:
        create_spec = TextWriteSpec(
            text=merged,
            insertion_point=request.output_insertion_point or first.insertion_point,
            layer=request.output_layer or first.layer,
            text_style=request.output_text_style or first.text_style,
            text_height=request.output_text_height or first.text_height,
            rotation_degrees=first.rotation_degrees,
        )
    return TextMergePlan(
        document_id=request.document_id,
        ordered_handles=tuple(item.handle for item in ordered),
        merged_text=merged,
        source_change=source_change,
        create_spec=create_spec,
        erase_handles=erase,
        destructive=request.source_policy is not MergeSourcePolicy.PRESERVE_ALL,
        dry_run=request.dry_run,
    )


class TextSizeMode(StrEnum):
    ABSOLUTE = "absolute"
    RATIO = "ratio"
    REFERENCE = "reference"


class TextSizeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    target_handles: tuple[str, ...] = Field(min_length=1)
    mode: TextSizeMode
    absolute_height: float | None = Field(default=None, gt=0)
    ratio: float | None = Field(default=None, gt=0)
    reference_handle: str | None = None
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> TextSizeRequest:
        _unique_handles(self.target_handles, "target_handles")
        supplied = sum(value is not None for value in (self.absolute_height, self.ratio, self.reference_handle))
        if supplied != 1:
            raise ValueError("TS requires exactly one height source")
        if self.mode is TextSizeMode.ABSOLUTE and self.absolute_height is None:
            raise ValueError("TS absolute mode requires absolute_height")
        if self.mode is TextSizeMode.RATIO and self.ratio is None:
            raise ValueError("TS ratio mode requires ratio")
        if self.mode is TextSizeMode.REFERENCE and self.reference_handle is None:
            raise ValueError("TS reference mode requires reference_handle")
        if not self.dry_run and not self.approval.approved:
            raise ValueError("TS execution requires explicit approval")
        return self


class TextSizePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "TS"
    legacy_symbol: str = "xiTsize"
    document_id: str
    mode: TextSizeMode
    changes: tuple[TextHeightChange, ...]
    destructive: bool = True
    dry_run: bool
    dialog_required: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


def plan_text_size(request: TextSizeRequest, entities: Sequence[TextEntitySnapshot]) -> TextSizePlan:
    selected = _selected_entities(request.target_handles, entities)
    by_handle = _snapshot_map(entities)
    reference_height: float | None = None
    if request.mode is TextSizeMode.REFERENCE:
        assert request.reference_handle is not None
        reference = by_handle.get(request.reference_handle.casefold())
        if reference is None:
            raise ValueError("TS reference entity not found")
        reference_height = reference.text_height
    changes: list[TextHeightChange] = []
    for entity in selected:
        if request.mode is TextSizeMode.ABSOLUTE:
            replacement = request.absolute_height
        elif request.mode is TextSizeMode.RATIO:
            replacement = entity.text_height * (request.ratio or 1.0)
        else:
            replacement = reference_height
        assert replacement is not None
        changes.append(
            TextHeightChange(
                handle=entity.handle,
                expected_height=entity.text_height,
                replacement_height=replacement,
            )
        )
    return TextSizePlan(
        document_id=request.document_id, mode=request.mode, changes=tuple(changes), dry_run=request.dry_run
    )


def register_headless_core_batch5_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(
        title="xiCAD Headless Core Batch 5 Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @mcp.tool(name="xicad_plan_numeric_text_format", annotations=read_only)
    def mcp_plan_numeric_text_format(
        request: NumericTextFormatRequest,
        entities: list[TextEntitySnapshot],
    ) -> NumericTextFormatPlan:
        return plan_numeric_text_format(request, entities)

    @mcp.tool(name="xicad_plan_group_numeric_operation", annotations=read_only)
    def mcp_plan_group_numeric_operation(request: GroupNumericRequest) -> GroupNumericPlan:
        return plan_group_numeric_operation(request)

    @mcp.tool(name="xicad_plan_bulk_number_calculation", annotations=read_only)
    def mcp_plan_bulk_number_calculation(
        request: BulkNumberCalculationRequest,
        entities: list[TextEntitySnapshot],
    ) -> BulkNumberCalculationPlan:
        return plan_bulk_number_calculation(request, entities)

    @mcp.tool(name="xicad_plan_square_metre_to_pyeong", annotations=read_only)
    def mcp_plan_square_metre_to_pyeong(request: SquareMetreToPyeongRequest) -> SquareMetreToPyeongPlan:
        return plan_square_metre_to_pyeong(request)

    @mcp.tool(name="xicad_plan_find_replace", annotations=read_only)
    def mcp_plan_find_replace(
        request: FindReplaceRequest,
        entities: list[TextEntitySnapshot],
    ) -> FindReplacePlan:
        return plan_find_replace(request, entities)

    @mcp.tool(name="xicad_plan_text_affix", annotations=read_only)
    def mcp_plan_text_affix(request: TextAffixRequest, entities: list[TextEntitySnapshot]) -> TextAffixPlan:
        return plan_text_affix(request, entities)

    @mcp.tool(name="xicad_plan_text_divide", annotations=read_only)
    def mcp_plan_text_divide(request: TextDivideRequest, source: TextEntitySnapshot) -> TextDividePlan:
        return plan_text_divide(request, source)

    @mcp.tool(name="xicad_plan_text_merge", annotations=read_only)
    def mcp_plan_text_merge(request: TextMergeRequest, entities: list[TextEntitySnapshot]) -> TextMergePlan:
        return plan_text_merge(request, entities)

    @mcp.tool(name="xicad_plan_text_size", annotations=read_only)
    def mcp_plan_text_size(request: TextSizeRequest, entities: list[TextEntitySnapshot]) -> TextSizePlan:
        return plan_text_size(request, entities)
