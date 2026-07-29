from decimal import Decimal

import pytest

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch5 import (
    BulkNumberCalculationRequest,
    BulkNumberOperation,
    DecimalPlacesPolicy,
    DelimiterOccurrence,
    DistributionMode,
    DrawingSpace,
    FindReplaceRequest,
    FindReplaceRule,
    GroupNumericOperation,
    GroupNumericRequest,
    MergeOrder,
    MergeSourcePolicy,
    NumericFormatMode,
    NumericTextFormatRequest,
    PyeongInput,
    PyeongOutputMode,
    RoundingMode,
    SplitMode,
    SquareMetreToPyeongRequest,
    TextAffixRequest,
    TextDivideRequest,
    TextEntityKind,
    TextEntitySnapshot,
    TextMatchMode,
    TextMergeRequest,
    TextSizeMode,
    TextSizeRequest,
    plan_bulk_number_calculation,
    plan_find_replace,
    plan_group_numeric_operation,
    plan_numeric_text_format,
    plan_square_metre_to_pyeong,
    plan_text_affix,
    plan_text_divide,
    plan_text_merge,
    plan_text_size,
)


def entity(handle: str, text: str, *, x: float = 0, y: float = 0, height: float = 2.5, layer: str = "TEXT"):
    return TextEntitySnapshot(
        handle=handle,
        text=text,
        kind=TextEntityKind.TEXT,
        layer=layer,
        text_style="Standard",
        text_height=height,
        insertion_point=Point3D(x=x, y=y),
        space=DrawingSpace.MODEL,
    )


def test_coi_inserts_commas_and_cor_removes_them_without_touching_decimals():
    source = entity("A", "면적 12345.67 / 1,234")
    coi = plan_numeric_text_format(
        NumericTextFormatRequest(document_id="D", target_handles=("A",), mode=NumericFormatMode.INSERT_COMMAS),
        [source],
    )
    assert coi.command_alias == "COI"
    assert coi.changes[0].replacement_text == "면적 12,345.67 / 1,234"
    cor = plan_numeric_text_format(
        NumericTextFormatRequest(document_id="D", target_handles=("A",), mode=NumericFormatMode.REMOVE_COMMAS),
        [entity("A", coi.changes[0].replacement_text)],
    )
    assert cor.command_alias == "COR"
    assert cor.changes[0].replacement_text == "면적 12345.67 / 1234"


def test_numeric_format_rejects_xref_or_locked_text():
    locked = entity("A", "1000").model_copy(update={"locked_layer": True})
    with pytest.raises(ValueError, match="locked-layer"):
        plan_numeric_text_format(
            NumericTextFormatRequest(document_id="D", target_handles=("A",), mode=NumericFormatMode.INSERT_COMMAS),
            [locked],
        )


def test_nd_divides_sums_and_rejects_zero_denominator():
    plan = plan_group_numeric_operation(
        GroupNumericRequest(
            operation=GroupNumericOperation.DIVIDE_GROUP_SUMS,
            first_group=(Decimal("10"), Decimal("20")),
            second_group=(Decimal("2"), Decimal("3")),
            decimal_places=2,
        )
    )
    assert plan.command_alias == "ND"
    assert plan.result == Decimal("6.00")
    with pytest.raises(ValueError, match="denominator"):
        plan_group_numeric_operation(
            GroupNumericRequest(
                operation=GroupNumericOperation.DIVIDE_GROUP_SUMS,
                first_group=(Decimal("1"),),
                second_group=(Decimal("0"),),
            )
        )


def test_ns_subtracts_group_sums():
    plan = plan_group_numeric_operation(
        GroupNumericRequest(
            operation=GroupNumericOperation.SUBTRACT_GROUP_SUMS,
            first_group=(Decimal("10"), Decimal("5")),
            second_group=(Decimal("3"), Decimal("2")),
        )
    )
    assert plan.command_alias == "NS"
    assert plan.exact_result == Decimal("10")


def test_np_requires_explicit_mode_and_supports_both_recovered_interpretations():
    with pytest.raises(ValueError, match="distribution_mode"):
        GroupNumericRequest(
            operation=GroupNumericOperation.DISTRIBUTION_CHECK,
            first_group=(Decimal("2"),),
            second_group=(Decimal("3"),),
        )
    group = plan_group_numeric_operation(
        GroupNumericRequest(
            operation=GroupNumericOperation.DISTRIBUTION_CHECK,
            first_group=(Decimal("2"), Decimal("3")),
            second_group=(Decimal("4"), Decimal("5")),
            distribution_mode=DistributionMode.GROUP_SUM_PRODUCT,
        )
    )
    pair = plan_group_numeric_operation(
        GroupNumericRequest(
            operation=GroupNumericOperation.DISTRIBUTION_CHECK,
            first_group=(Decimal("2"), Decimal("3")),
            second_group=(Decimal("4"), Decimal("5")),
            distribution_mode=DistributionMode.PAIRWISE_PRODUCT_SUM,
        )
    )
    assert group.exact_result == Decimal("45")
    assert pair.exact_result == Decimal("23")


def test_nuc_applies_explicit_operation_rounding_and_comma_policy():
    request = BulkNumberCalculationRequest(
        document_id="D",
        target_handles=("A",),
        operation=BulkNumberOperation.MULTIPLY,
        operand=Decimal("1.1"),
        decimal_places_policy=DecimalPlacesPolicy.FIXED,
        decimal_places=2,
        rounding_mode=RoundingMode.HALF_UP,
        thousands_separator=True,
    )
    plan = plan_bulk_number_calculation(request, [entity("A", "금액 1234.5")])
    assert plan.changes[0].replacement_text == "금액 1,357.95"


def test_nuc_recognizes_parenthesized_negative_only_when_enabled():
    request = BulkNumberCalculationRequest(
        document_id="D",
        target_handles=("A",),
        operation=BulkNumberOperation.ADD,
        operand=Decimal("10"),
        decimal_places_policy=DecimalPlacesPolicy.PRESERVE_INPUT,
        rounding_mode=RoundingMode.HALF_UP,
        recognize_parenthesized_negative=True,
    )
    plan = plan_bulk_number_calculation(request, [entity("A", "(100.0)")])
    assert plan.changes[0].replacement_text == "(90.0)"


def test_nuc_fixed_policy_and_division_safety_are_validated():
    with pytest.raises(ValueError, match="decimal_places"):
        BulkNumberCalculationRequest(
            document_id="D",
            target_handles=("A",),
            operation=BulkNumberOperation.ADD,
            operand=Decimal("1"),
            decimal_places_policy=DecimalPlacesPolicy.FIXED,
        )
    with pytest.raises(ValueError, match="divisor"):
        BulkNumberCalculationRequest(
            document_id="D",
            target_handles=("A",),
            operation=BulkNumberOperation.DIVIDE,
            operand=Decimal("0"),
            decimal_places_policy=DecimalPlacesPolicy.PRESERVE_INPUT,
        )


def test_py_uses_recovered_03025_factor_and_explicit_rendering():
    plan = plan_square_metre_to_pyeong(
        SquareMetreToPyeongRequest(
            document_id="D",
            inputs=(PyeongInput(source_handle="A", square_metres=Decimal("100")),),
            output_mode=PyeongOutputMode.CREATE_NEW,
            insertion_points=(Point3D(x=10, y=20),),
            decimal_places=2,
            rounding_mode=RoundingMode.HALF_UP,
            thousands_separator=False,
            unit_text=" 평",
            include_parentheses=True,
            output_layer="TEXT",
            output_text_style="Standard",
            output_text_height=2.5,
        )
    )
    assert plan.outputs[0].exact_pyeong == Decimal("30.2500")
    assert plan.outputs[0].rendered_text == "(30.25 평)"
    assert plan.outputs[0].create_spec is not None


def test_py_requires_output_cardinality():
    with pytest.raises(ValueError, match="one target"):
        SquareMetreToPyeongRequest(
            document_id="D",
            inputs=(PyeongInput(source_handle="A", square_metres=Decimal("1")),),
            output_mode=PyeongOutputMode.UPDATE_TARGET,
            decimal_places=2,
            rounding_mode=RoundingMode.HALF_UP,
            thousands_separator=False,
            unit_text=" 평",
            include_parentheses=False,
            output_layer="TEXT",
            output_text_style="Standard",
            output_text_height=2.5,
        )


def test_far_whole_case_insensitive_search_only_does_not_mutate():
    request = FindReplaceRequest(
        document_id="D",
        target_handles=("A", "B"),
        rules=(FindReplaceRule(old="room", new="SPACE"),),
        match_mode=TextMatchMode.WHOLE,
        case_sensitive=False,
        ignore_spaces=False,
        search_only=True,
        allowed_kinds=(TextEntityKind.TEXT,),
    )
    plan = plan_find_replace(request, [entity("A", "ROOM"), entity("B", "room 1")])
    assert [record.handle for record in plan.records] == ["A"]
    assert not plan.records[0].changed
    assert not plan.destructive


def test_far_substring_filters_layer_and_preserves_case_insensitive_replacement():
    request = FindReplaceRequest(
        document_id="D",
        target_handles=("A", "B"),
        rules=(FindReplaceRule(old="old", new="NEW"),),
        match_mode=TextMatchMode.SUBSTRING,
        case_sensitive=False,
        ignore_spaces=False,
        search_only=False,
        allowed_kinds=(TextEntityKind.TEXT,),
        allowed_layers=("TARGET",),
    )
    plan = plan_find_replace(request, [entity("A", "Old value", layer="TARGET"), entity("B", "old", layer="OTHER")])
    assert plan.records[0].result_text == "NEW value"
    assert plan.skipped_handles == ("B",)


def test_far_ignore_spaces_is_restricted_to_whole_match():
    with pytest.raises(ValueError, match="whole-string"):
        FindReplaceRequest(
            document_id="D",
            target_handles=("A",),
            rules=(FindReplaceRule(old="a b", new="c"),),
            match_mode=TextMatchMode.SUBSTRING,
            case_sensitive=True,
            ignore_spaces=True,
            search_only=True,
            allowed_kinds=(TextEntityKind.TEXT,),
        )


def test_tap_adds_explicit_prefix_and_suffix():
    plan = plan_text_affix(
        TextAffixRequest(document_id="D", target_handles=("A",), prefix="[", suffix="]", trim_existing=True),
        [entity("A", "  ROOM  ")],
    )
    assert plan.changes[0].replacement_text == "[ROOM]"


def test_td_splits_by_delimiter_and_can_preserve_source():
    plan = plan_text_divide(
        TextDivideRequest(
            document_id="D",
            source_handle="A",
            split_mode=SplitMode.DELIMITER,
            delimiter=":",
            delimiter_occurrence=DelimiterOccurrence.FIRST,
            preserve_original=True,
            trim_original_part=True,
            trim_new_part=True,
            between_text="",
            new_insertion_point=Point3D(x=0, y=-4),
            new_line_gap_multiplier=1.6,
        ),
        entity("A", "Room: 101"),
    )
    assert plan.source_change is None
    assert plan.create_spec.text == "101"
    assert not plan.destructive


def test_td_rejects_edge_split():
    with pytest.raises(ValueError, match="inside"):
        plan_text_divide(
            TextDivideRequest(
                document_id="D",
                source_handle="A",
                split_mode=SplitMode.INDEX,
                split_index=4,
                preserve_original=False,
                trim_original_part=False,
                trim_new_part=False,
                between_text="",
                new_insertion_point=Point3D(x=0, y=0),
                new_line_gap_multiplier=1.6,
            ),
            entity("A", "Room"),
        )


def test_tm_orders_left_to_right_and_creates_new_without_erasing_sources():
    plan = plan_text_merge(
        TextMergeRequest(
            document_id="D",
            ordered_handles=("B", "A"),
            order=MergeOrder.LEFT_TO_RIGHT,
            separator=" / ",
            source_policy=MergeSourcePolicy.PRESERVE_ALL,
            output_insertion_point=Point3D(x=0, y=0),
        ),
        [entity("A", "LEFT", x=0), entity("B", "RIGHT", x=10)],
    )
    assert plan.ordered_handles == ("A", "B")
    assert plan.merged_text == "LEFT / RIGHT"
    assert plan.erase_handles == ()
    assert plan.create_spec is not None


def test_tm_destructive_policy_requires_approval_for_live_execution():
    with pytest.raises(ValueError, match="approval"):
        TextMergeRequest(
            document_id="D",
            ordered_handles=("A", "B"),
            order=MergeOrder.AS_GIVEN,
            separator="",
            source_policy=MergeSourcePolicy.REPLACE_FIRST_ERASE_REST,
            dry_run=False,
        )


def test_ts_supports_absolute_ratio_and_reference_modes():
    entities = [entity("A", "a", height=2), entity("B", "b", height=4), entity("R", "r", height=7)]
    absolute = plan_text_size(
        TextSizeRequest(document_id="D", target_handles=("A",), mode=TextSizeMode.ABSOLUTE, absolute_height=5),
        entities,
    )
    ratio = plan_text_size(
        TextSizeRequest(document_id="D", target_handles=("A", "B"), mode=TextSizeMode.RATIO, ratio=2),
        entities,
    )
    reference = plan_text_size(
        TextSizeRequest(document_id="D", target_handles=("A",), mode=TextSizeMode.REFERENCE, reference_handle="R"),
        entities,
    )
    assert absolute.changes[0].replacement_height == 5
    assert [change.replacement_height for change in ratio.changes] == [4, 8]
    assert reference.changes[0].replacement_height == 7


def test_mutating_live_requests_require_fingerprinted_approval():
    with pytest.raises(ValueError, match="approval"):
        TextAffixRequest(
            document_id="D",
            target_handles=("A",),
            prefix="x",
            suffix="",
            dry_run=False,
        )
    request = TextAffixRequest(
        document_id="D",
        target_handles=("A",),
        prefix="x",
        suffix="",
        dry_run=False,
        approval=Approval(approved=True, fingerprint="sha256:test"),
    )
    assert request.approval.approved
