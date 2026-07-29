from __future__ import annotations

import ast
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ArithmeticOperation(StrEnum):
    ADD = "add"
    SUBTRACT = "subtract"
    DIVIDE = "divide"


class PercentageMode(StrEnum):
    OF = "of"
    INCREASE = "increase"
    DECREASE = "decrease"
    RATIO = "ratio"


class DecimalResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    exact_result: Decimal
    result: Decimal
    decimal_places: int | None
    cad_required: bool = False
    dialog_required: bool = False
    deterministic: bool = True
    production_usable: bool = True


class ArithmeticSequenceRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    operation: ArithmeticOperation
    operands: tuple[Decimal, ...] = Field(min_length=2)
    decimal_places: int | None = Field(default=None, ge=0, le=12)


class PercentageRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    mode: PercentageMode
    base: Decimal
    value: Decimal
    decimal_places: int | None = Field(default=None, ge=0, le=12)

    @model_validator(mode="after")
    def validate_ratio(self) -> PercentageRequest:
        if self.mode is PercentageMode.RATIO and self.base == 0:
            raise ValueError("percentage ratio base must not be zero")
        return self


class CalculatorRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    expression: str = Field(min_length=1, max_length=1000)
    variables: dict[str, Decimal] = Field(default_factory=dict)
    decimal_places: int | None = Field(default=None, ge=0, le=12)

    @field_validator("expression")
    @classmethod
    def strip_expression(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("expression must not be blank")
        return value

    @field_validator("variables")
    @classmethod
    def validate_variables(cls, value: dict[str, Decimal]) -> dict[str, Decimal]:
        for name in value:
            if not name.isidentifier() or name.startswith("_"):
                raise ValueError(f"invalid variable name: {name}")
        return value


class CalculatorResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "00"
    legacy_symbol: str = "xiCalculator"
    expression: str
    variables: dict[str, Decimal]
    exact_result: Decimal
    result: Decimal
    decimal_places: int | None
    cad_required: bool = False
    dialog_required: bool = False
    deterministic: bool = True
    production_usable: bool = True


class CalculationEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    label: str = Field(min_length=1, max_length=120)
    expression: str = Field(min_length=1, max_length=1000)


class MultiCalculationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    entries: tuple[CalculationEntry, ...] = Field(min_length=1, max_length=100)
    variables: dict[str, Decimal] = Field(default_factory=dict)
    decimal_places: int | None = Field(default=None, ge=0, le=12)

    @model_validator(mode="after")
    def validate_request(self) -> MultiCalculationRequest:
        labels = [entry.label.casefold() for entry in self.entries]
        if len(labels) != len(set(labels)):
            raise ValueError("calculation labels must be unique")
        CalculatorRequest(expression="0", variables=self.variables)
        return self


class CalculationRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    label: str
    expression: str
    exact_result: Decimal
    result: Decimal


class MultiCalculationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str = "ABC"
    legacy_symbol: str = "xiABC"
    records: tuple[CalculationRecord, ...]
    decimal_places: int | None
    cad_required: bool = False
    dialog_required: bool = False
    deterministic: bool = True
    production_usable: bool = True


def _round(value: Decimal, places: int | None) -> Decimal:
    if places is None:
        return value
    quantum = Decimal(1).scaleb(-places)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def calculate_sequence(request: ArithmeticSequenceRequest) -> DecimalResult:
    first, *rest = request.operands
    value = first
    if request.operation is ArithmeticOperation.ADD:
        for operand in rest:
            value += operand
        alias, symbol = "=", "xiAddition"
    elif request.operation is ArithmeticOperation.SUBTRACT:
        for operand in rest:
            value -= operand
        alias, symbol = "-", "xiSubtraction"
    else:
        for operand in rest:
            if operand == 0:
                raise ValueError("division by zero")
            value /= operand
        alias, symbol = "/", "xiDivision"
    return DecimalResult(
        command_alias=alias,
        legacy_symbol=symbol,
        exact_result=value,
        result=_round(value, request.decimal_places),
        decimal_places=request.decimal_places,
    )


def calculate_percentage(request: PercentageRequest) -> DecimalResult:
    hundred = Decimal(100)
    if request.mode is PercentageMode.OF:
        value = request.base * request.value / hundred
    elif request.mode is PercentageMode.INCREASE:
        value = request.base * (Decimal(1) + request.value / hundred)
    elif request.mode is PercentageMode.DECREASE:
        value = request.base * (Decimal(1) - request.value / hundred)
    else:
        value = request.value / request.base * hundred
    return DecimalResult(
        command_alias="%",
        legacy_symbol="xiPercent",
        exact_result=value,
        result=_round(value, request.decimal_places),
        decimal_places=request.decimal_places,
    )


_ALLOWED_BINOPS: dict[type[ast.operator], Any] = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b if b != 0 else (_raise_zero()),
    ast.Mod: lambda a, b: a % b if b != 0 else (_raise_zero()),
}


def _raise_zero() -> Decimal:
    raise ValueError("division by zero")


def _literal_decimal(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("only numeric literals are allowed")
    return Decimal(str(value))


def _eval_node(node: ast.AST, variables: dict[str, Decimal], depth: int = 0) -> Decimal:
    if depth > 50:
        raise ValueError("expression nesting is too deep")
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, variables, depth + 1)
    if isinstance(node, ast.Constant):
        return _literal_decimal(node.value)
    if isinstance(node, ast.Name):
        try:
            return variables[node.id]
        except KeyError as exc:
            raise ValueError(f"unknown variable: {node.id}") from exc
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval_node(node.operand, variables, depth + 1)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _eval_node(node.left, variables, depth + 1)
        right = _eval_node(node.right, variables, depth + 1)
        return _ALLOWED_BINOPS[type(node.op)](left, right)
    raise ValueError(f"unsupported expression element: {type(node).__name__}")


def evaluate_expression(request: CalculatorRequest) -> CalculatorResult:
    try:
        tree = ast.parse(request.expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("invalid arithmetic expression") from exc
    exact = _eval_node(tree, request.variables)
    return CalculatorResult(
        expression=request.expression,
        variables=request.variables,
        exact_result=exact,
        result=_round(exact, request.decimal_places),
        decimal_places=request.decimal_places,
    )


def evaluate_multiple(request: MultiCalculationRequest) -> MultiCalculationResult:
    records: list[CalculationRecord] = []
    for entry in request.entries:
        result = evaluate_expression(
            CalculatorRequest(
                expression=entry.expression,
                variables=request.variables,
                decimal_places=request.decimal_places,
            )
        )
        records.append(
            CalculationRecord(
                label=entry.label,
                expression=entry.expression,
                exact_result=result.exact_result,
                result=result.result,
            )
        )
    return MultiCalculationResult(records=tuple(records), decimal_places=request.decimal_places)


def register_headless_core_batch4_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(
        title="xiCAD Headless Arithmetic Core",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @mcp.tool(
        name="xicad_calculate_sequence",
        description="Run dialog-free legacy =, -, or / decimal arithmetic. No CAD access is required.",
        annotations=read_only,
    )
    def mcp_calculate_sequence(request: ArithmeticSequenceRequest) -> DecimalResult:
        return calculate_sequence(request)

    @mcp.tool(
        name="xicad_calculate_percentage",
        description="Run dialog-free legacy % arithmetic with an explicit percentage mode.",
        annotations=read_only,
    )
    def mcp_calculate_percentage(request: PercentageRequest) -> DecimalResult:
        return calculate_percentage(request)

    @mcp.tool(
        name="xicad_calculator",
        description="Evaluate a safe dialog-free 00 arithmetic expression. Function calls, attributes, and arbitrary Python are rejected.",
        annotations=read_only,
    )
    def mcp_calculator(request: CalculatorRequest) -> CalculatorResult:
        return evaluate_expression(request)

    @mcp.tool(
        name="xicad_multi_calculator",
        description="Evaluate a labeled batch of safe arithmetic expressions for legacy ABC.",
        annotations=read_only,
    )
    def mcp_multi_calculator(request: MultiCalculationRequest) -> MultiCalculationResult:
        return evaluate_multiple(request)
