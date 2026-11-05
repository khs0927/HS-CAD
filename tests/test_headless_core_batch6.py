from decimal import Decimal

import pytest

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch5 import TextEntityKind, TextEntitySnapshot
from xicad_mcp.headless_core_batch6 import (
    AffixPlacement,
    AggregateLayout,
    AggregateSourceKind,
    AreaOutputMode,
    AutoNumberingRequest,
    Batch6RoundingMode,
    CurveKind,
    CurveLengthSnapshot,
    EmbeddedNumberIncrementRequest,
    ExistingNumberPolicy,
    IndividualDistanceMode,
    LengthUnit,
    LevelMoveAddRequest,
    LevelMoveMode,
    LevelNumberAddRequest,
    LineSumRequest,
    NumberBase,
    NumberObjectKind,
    NumberPlacement,
    NumberSequenceSpec,
    NumIncRequest,
    PickNumberIncrementRequest,
    PyeongInput,
    PyeongToSquareMetreRequest,
    QuickDistanceRequest,
    SymbolAggregateRequest,
    SymbolNumberRecord,
    TargetOrder,
    TextAlignment,
    TextIncrementInputRequest,
    generate_number_sequence,
    plan_auto_numbering,
    plan_embedded_number_increment,
    plan_level_move_add,
    plan_level_number_add,
    plan_line_sum,
    plan_num_inc,
    plan_pick_number_increment,
    plan_pyeong_to_square_metres,
    plan_quick_distance,
    plan_symbol_aggregate,
    plan_text_increment_input,
)


def entity(handle: str, text: str, *, x: float = 0, y: float = 0, kind=TextEntityKind.TEXT):
    return TextEntitySnapshot(
        handle=handle,
        text=text,
        kind=kind,
        layer="TEXT",
        text_style="Standard",
        text_height=2.5,
        insertion_point=Point3D(x=x, y=y),
    )


def approved() -> Approval:
    return Approval(approved=True, fingerprint="sha256:test")


def test_m2_uses_reciprocal_of_recovered_03025_factor():
    plan = plan_pyeong_to_square_metres(
        PyeongToSquareMetreRequest(
            document_id="D",
            inputs=(PyeongInput(pyeong=Decimal("30.25")),),
            output_mode=AreaOutputMode.RETURN_ONLY,
            decimal_places=2,
            rounding_mode=Batch6RoundingMode.HALF_UP,
        )
    )
    assert plan.outputs[0].exact_square_metres == Decimal("100")
    assert plan.outputs[0].rendered_text == "100.00 ㎡"
    assert not plan.production_usable


def test_m2_create_requires_point_and_live_approval():
    with pytest.raises(ValueError, match="insertion_point"):
        PyeongToSquareMetreRequest(
            document_id="D",
            inputs=(PyeongInput(pyeong=Decimal("1")),),
            output_mode=AreaOutputMode.CREATE_NEW,
            decimal_places=2,
            rounding_mode=Batch6RoundingMode.HALF_UP,
        )
    with pytest.raises(ValueError, match="approval"):
        PyeongToSquareMetreRequest(
            document_id="D",
            inputs=(PyeongInput(pyeong=Decimal("1"), insertion_point=Point3D(x=0, y=0)),),
            output_mode=AreaOutputMode.CREATE_NEW,
            decimal_places=2,
            rounding_mode=Batch6RoundingMode.HALF_UP,
            dry_run=False,
        )


def test_ina_aggregates_symbols_case_insensitively_and_preserves_order():
    plan = plan_symbol_aggregate(
        SymbolAggregateRequest(
            document_id="D",
            records=(
                SymbolNumberRecord(symbol="A", quantity=Decimal("2"), source_handles=("1",)),
                SymbolNumberRecord(symbol="a", quantity=Decimal("3"), source_handles=("2",)),
                SymbolNumberRecord(symbol="B", quantity=Decimal("1")),
            ),
            source_kind=AggregateSourceKind.TEXT_PAIR,
            layout=AggregateLayout.ONE_TEXT,
            decimal_places=0,
        ),
        command_alias="INA",
    )
    assert [row.symbol for row in plan.rows] == ["A", "B"]
    assert plan.rows[0].total == Decimal("5")
    assert plan.rendered_texts == ("A / 5", "B / 1")


def test_spn_two_text_layout_and_recalc_metadata_are_explicit():
    plan = plan_symbol_aggregate(
        SymbolAggregateRequest(
            document_id="D",
            records=(SymbolNumberRecord(symbol="○", quantity=Decimal("4")),),
            source_kind=AggregateSourceKind.NORMALIZED_INPUT,
            layout=AggregateLayout.TWO_TEXTS,
            store_recalculation_metadata=True,
        ),
        command_alias="SPN",
    )
    assert plan.command_alias == "SPN"
    assert plan.rendered_texts == ("○", "4")
    assert plan.store_recalculation_metadata


def test_lis_sums_supported_curve_snapshots_and_converts_to_metres():
    curves = [
        CurveLengthSnapshot(handle="A", kind=CurveKind.LINE, layer="L1", length_drawing_units=Decimal("1000")),
        CurveLengthSnapshot(handle="B", kind=CurveKind.ARC, layer="L1", length_drawing_units=Decimal("500")),
    ]
    plan = plan_line_sum(
        LineSumRequest(
            document_id="D",
            target_handles=("A", "B"),
            output_unit=LengthUnit.METRE,
            decimal_places=2,
            include_formula=True,
            group_by_layer=True,
        ),
        curves,
    )
    assert plan.total_output_units == Decimal("1.5")
    assert plan.formula == "1.00 + 0.50"
    assert plan.rendered_text.endswith("= 1.50m")
    assert plan.layer_totals[0].total == Decimal("1.5")


def test_lis_rejects_xref_curve():
    with pytest.raises(ValueError, match="xref"):
        plan_line_sum(
            LineSumRequest(document_id="D", target_handles=("A",), output_unit=LengthUnit.MILLIMETRE),
            [
                CurveLengthSnapshot(
                    handle="A", kind=CurveKind.LINE, layer="X", length_drawing_units=Decimal("1"), is_xref=True
                )
            ],
        )


def test_lma_move_updates_level_text_and_requests_geometry_move():
    plan = plan_level_move_add(
        LevelMoveAddRequest(
            document_id="D",
            target_handles=("A",),
            mode=LevelMoveMode.MOVE,
            translation=Point3D(x=0, y=100),
            level_delta=Decimal("3.5"),
            decimal_places=2,
        ),
        [entity("A", "EL: +35.32")],
    )
    assert plan.text_changes[0].replacement_text == "EL: +38.82"
    assert plan.move_handles == ("A",)
    assert plan.translation.y == 100


def test_lma_copy_preserves_source_and_creates_translated_text():
    plan = plan_level_move_add(
        LevelMoveAddRequest(
            document_id="D",
            target_handles=("A",),
            mode=LevelMoveMode.COPY,
            translation=Point3D(x=10, y=20),
            level_delta=Decimal("1"),
            decimal_places=2,
        ),
        [entity("A", "EL -1.00", x=5, y=6)],
    )
    assert plan.text_changes == ()
    assert plan.create_specs[0].text == "EL 0.00"
    assert plan.create_specs[0].insertion_point == Point3D(x=15, y=26, z=0)


def test_lna_changes_only_selected_numeric_token():
    plan = plan_level_number_add(
        LevelNumberAddRequest(
            document_id="D",
            target_handles=("A",),
            delta=Decimal("-2"),
            decimal_places=1,
        ),
        [entity("A", "LEVEL 2 / EL +10.0")],
    )
    assert plan.text_changes[0].replacement_text == "LEVEL 2 / EL +8.0"


def test_level_commands_require_numeric_token():
    with pytest.raises(ValueError, match="no numeric token"):
        plan_level_number_add(
            LevelNumberAddRequest(document_id="D", target_handles=("A",), delta=Decimal("1")),
            [entity("A", "NO LEVEL")],
        )


def test_qd_computes_segments_skips_explicit_index_and_builds_formula():
    plan = plan_quick_distance(
        QuickDistanceRequest(
            document_id="D",
            points=(Point3D(x=0, y=0), Point3D(x=3, y=4), Point3D(x=6, y=8)),
            skipped_segment_indices=(1,),
            output_unit=LengthUnit.MILLIMETRE,
            decimal_places=1,
            include_formula=True,
        )
    )
    assert plan.total_output_length == Decimal("5.0")
    assert plan.formula == "5.0"
    assert plan.segments[1].skipped


def test_qd_live_dimension_mode_requires_approval():
    with pytest.raises(ValueError, match="approval"):
        QuickDistanceRequest(
            document_id="D",
            points=(Point3D(x=0, y=0), Point3D(x=1, y=0)),
            output_unit=LengthUnit.MILLIMETRE,
            individual_mode=IndividualDistanceMode.DIMENSION,
            dry_run=False,
        )


def test_sequence_supports_hex_step_and_leading_zero_policy():
    generated = generate_number_sequence(
        NumberSequenceSpec(start="0A", step=1, count=3, base=NumberBase.HEXADECIMAL, prefix="P-", suffix="")
    )
    assert [item.rendered_text for item in generated] == ["P-0A", "P-0B", "P-0C"]


def test_sequence_rejects_invalid_base_value():
    with pytest.raises(ValueError, match="invalid octal"):
        NumberSequenceSpec(start="09", step=1, count=1, base=NumberBase.OCTAL)


def test_numc_generates_explicit_writes_without_interactive_dialog():
    plan = plan_num_inc(
        NumIncRequest(
            document_id="D",
            sequence=NumberSequenceSpec(start="01", step=1, count=2, prefix="A-"),
            placements=(
                NumberPlacement(point=Point3D(x=0, y=0)),
                NumberPlacement(point=Point3D(x=10, y=0), rotation_degrees=90),
            ),
            object_kind=NumberObjectKind.TEXT,
            layer="NUM",
            text_height=2.5,
            alignment=TextAlignment.CENTER,
        )
    )
    assert [write.text for write in plan.writes] == ["A-01", "A-02"]
    assert plan.writes[1].rotation_degrees == 90
    assert not plan.cad_mutation_tool_exposed


def test_numc_block_requires_explicit_block_and_attribute():
    with pytest.raises(ValueError, match="block_name"):
        NumIncRequest(
            document_id="D",
            sequence=NumberSequenceSpec(start="1", step=1, count=1),
            placements=(NumberPlacement(point=Point3D(x=0, y=0)),),
            object_kind=NumberObjectKind.BLOCK_ATTRIBUTE,
            layer="NUM",
            text_height=2.5,
        )


def test_tic_orders_left_to_right_and_replaces_numbers():
    request = AutoNumberingRequest(
        document_id="D",
        target_handles=("B", "A"),
        sequence=NumberSequenceSpec(start="01", step=1, count=2, prefix="N"),
        order=TargetOrder.LEFT_TO_RIGHT,
        number_policy=ExistingNumberPolicy.REPLACE,
    )
    plan = plan_auto_numbering(request, [entity("A", "ROOM 7", x=0), entity("B", "ROOM 8", x=10)])
    assert plan.ordered_handles == ("A", "B")
    assert [change.replacement_text for change in plan.changes] == ["ROOM N01", "ROOM N02"]


def test_tic_add_policy_can_append_when_no_numeric_token():
    request = AutoNumberingRequest(
        document_id="D",
        target_handles=("A",),
        sequence=NumberSequenceSpec(start="1", step=1, count=1, prefix="-"),
        number_policy=ExistingNumberPolicy.ADD,
    )
    plan = plan_auto_numbering(request, [entity("A", "ROOM")])
    assert plan.changes[0].replacement_text == "ROOM-1"


def test_tie_preserves_source_and_creates_numbered_copy():
    plan = plan_pick_number_increment(
        PickNumberIncrementRequest(
            document_id="D",
            source_handles=("A",),
            sequence=NumberSequenceSpec(start="1", step=1, count=1),
            placement=AffixPlacement.FRONT,
            separator=": ",
            copy_offset=Point3D(x=5, y=0),
        ),
        [entity("A", "ROOM", x=1, y=2)],
    )
    assert plan.changes == ()
    assert plan.create_specs[0].text == "1: ROOM"
    assert plan.create_specs[0].insertion_point.x == 6


def test_tii_creates_english_numeric_sequence_at_explicit_points():
    plan = plan_text_increment_input(
        TextIncrementInputRequest(
            document_id="D",
            sequence=NumberSequenceSpec(start="1", step=1, count=2, prefix="A", suffix="-X"),
            placements=(
                NumberPlacement(point=Point3D(x=0, y=0)),
                NumberPlacement(point=Point3D(x=20, y=0)),
            ),
            layer="TEXT",
            text_height=2.5,
        )
    )
    assert [spec.text for spec in plan.create_specs] == ["A1-X", "A2-X"]


def test_tin_replaces_embedded_number_in_mtext_and_attribute():
    request = EmbeddedNumberIncrementRequest(
        document_id="D",
        target_handles=("A", "B"),
        sequence=NumberSequenceSpec(start="10", step=5, count=2, prefix="#"),
    )
    plan = plan_embedded_number_increment(
        request,
        [entity("A", "ITEM 1", kind=TextEntityKind.MTEXT), entity("B", "TAG=2", kind=TextEntityKind.ATTRIB)],
    )
    assert [c.replacement_text for c in plan.changes] == ["ITEM #10", "TAG=#15"]


def test_tin_rejects_disallowed_kind():
    with pytest.raises(ValueError, match="kind"):
        plan_embedded_number_increment(
            EmbeddedNumberIncrementRequest(
                document_id="D",
                target_handles=("A",),
                sequence=NumberSequenceSpec(start="1", step=1, count=1),
            ),
            [entity("A", "1", kind=TextEntityKind.TABLE_CELL)],
        )


def test_all_mutating_batch6_requests_remain_dry_run_planners():
    plan = plan_num_inc(
        NumIncRequest(
            document_id="D",
            sequence=NumberSequenceSpec(start="1", step=1, count=1),
            placements=(NumberPlacement(point=Point3D(x=0, y=0)),),
            layer="TEXT",
            text_height=2.5,
        )
    )
    assert plan.dry_run
    assert not plan.legacy_equivalence_verified_in_cad
    assert not plan.production_usable
