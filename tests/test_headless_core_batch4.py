from decimal import Decimal

import pytest

from xicad_mcp.headless_core_batch4 import (
    ArithmeticOperation,
    ArithmeticSequenceRequest,
    CalculationEntry,
    CalculatorRequest,
    MultiCalculationRequest,
    PercentageMode,
    PercentageRequest,
    calculate_percentage,
    calculate_sequence,
    evaluate_expression,
    evaluate_multiple,
)


def test_addition_alias_is_equals_and_uses_decimal_exactness():
    result = calculate_sequence(
        ArithmeticSequenceRequest(
            operation=ArithmeticOperation.ADD,
            operands=(Decimal("0.1"), Decimal("0.2"), Decimal("0.3")),
        )
    )
    assert result.command_alias == "="
    assert result.exact_result == Decimal("0.6")
    assert result.production_usable


def test_subtraction_is_left_associative():
    result = calculate_sequence(
        ArithmeticSequenceRequest(
            operation=ArithmeticOperation.SUBTRACT,
            operands=(Decimal("10"), Decimal("2"), Decimal("3")),
        )
    )
    assert result.command_alias == "-"
    assert result.result == Decimal("5")


def test_division_is_left_associative_and_rejects_zero():
    result = calculate_sequence(
        ArithmeticSequenceRequest(
            operation=ArithmeticOperation.DIVIDE,
            operands=(Decimal("20"), Decimal("2"), Decimal("5")),
        )
    )
    assert result.command_alias == "/"
    assert result.result == Decimal("2")
    with pytest.raises(ValueError, match="zero"):
        calculate_sequence(
            ArithmeticSequenceRequest(
                operation=ArithmeticOperation.DIVIDE,
                operands=(Decimal("1"), Decimal("0")),
            )
        )


def test_percentage_of_increase_decrease_and_ratio_are_explicit():
    assert calculate_percentage(
        PercentageRequest(mode=PercentageMode.OF, base=Decimal("200"), value=Decimal("10"))
    ).result == Decimal("20")
    assert calculate_percentage(
        PercentageRequest(mode=PercentageMode.INCREASE, base=Decimal("200"), value=Decimal("10"))
    ).result == Decimal("220.0")
    assert calculate_percentage(
        PercentageRequest(mode=PercentageMode.DECREASE, base=Decimal("200"), value=Decimal("10"))
    ).result == Decimal("180.0")
    assert calculate_percentage(
        PercentageRequest(mode=PercentageMode.RATIO, base=Decimal("200"), value=Decimal("50"))
    ).result == Decimal("25.00")


def test_percentage_ratio_rejects_zero_base():
    with pytest.raises(ValueError, match="base"):
        PercentageRequest(mode=PercentageMode.RATIO, base=Decimal("0"), value=Decimal("1"))


def test_calculator_supports_parentheses_variables_and_rounding():
    result = evaluate_expression(
        CalculatorRequest(
            expression="(width * depth) / count",
            variables={"width": Decimal("3.2"), "depth": Decimal("4.5"), "count": Decimal("3")},
            decimal_places=2,
        )
    )
    assert result.exact_result == Decimal("4.80")
    assert result.result == Decimal("4.80")
    assert result.command_alias == "00"


def test_calculator_rejects_calls_attributes_and_power():
    for expression in ["__import__('os')", "a.real", "2 ** 100"]:
        with pytest.raises(ValueError, match="unsupported"):
            evaluate_expression(CalculatorRequest(expression=expression, variables={"a": Decimal("1")}))


def test_calculator_rejects_unknown_variable_and_zero_division():
    with pytest.raises(ValueError, match="unknown variable"):
        evaluate_expression(CalculatorRequest(expression="x + 1"))
    with pytest.raises(ValueError, match="zero"):
        evaluate_expression(CalculatorRequest(expression="1 / 0"))


def test_multi_calculator_returns_labeled_records_in_input_order():
    result = evaluate_multiple(
        MultiCalculationRequest(
            entries=(
                CalculationEntry(label="area", expression="w * h"),
                CalculationEntry(label="perimeter", expression="2 * (w + h)"),
            ),
            variables={"w": Decimal("3"), "h": Decimal("4")},
        )
    )
    assert result.command_alias == "ABC"
    assert [(r.label, r.result) for r in result.records] == [
        ("area", Decimal("12")),
        ("perimeter", Decimal("14")),
    ]


def test_multi_calculator_rejects_duplicate_labels():
    with pytest.raises(ValueError, match="unique"):
        MultiCalculationRequest(
            entries=(
                CalculationEntry(label="A", expression="1"),
                CalculationEntry(label="a", expression="2"),
            )
        )
