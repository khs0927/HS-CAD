import pytest

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch9 import LayerEntitySnapshot, LayerSnapshot
from xicad_mcp.headless_core_batch11 import (
    AllLayerStateRequest,
    BaselineSide,
    ContinueDimensionRequest,
    ContinueGapSource,
    DimensionConvertRequest,
    DimensionExtensionToggleRequest,
    DimensionGapRequest,
    DimensionKind,
    DimensionScaleBasis,
    DimensionSnapshot,
    DimensionSourceDisposition,
    DimensionTextEditRequest,
    DimensionTextHomeRequest,
    DimensionTextMode,
    ExtensionArrangeRequest,
    ExtensionLengthRequest,
    ExtensionLineTarget,
    LinearDimensionKind,
    SelectedLayerUnlockRequest,
    SuppressionOperation,
    plan_all_layers_thaw,
    plan_all_layers_unlock,
    plan_continue_dimension,
    plan_dimension_convert,
    plan_dimension_extension_toggle,
    plan_dimension_gap,
    plan_dimension_text_edit,
    plan_dimension_text_home,
    plan_extension_arrange,
    plan_extension_length,
    plan_selected_layers_unlock,
    plan_toggle_layer_on_off,
    register_headless_core_batch11_tools,
)


def layer(name: str, **kwargs):
    return LayerSnapshot(name=name, color_index=7, linetype="Continuous", **kwargs)


def dimension(handle: str, *, kind=DimensionKind.ALIGNED, x=0, suppressed1=False, suppressed2=False):
    return DimensionSnapshot(
        handle=handle,
        kind=kind,
        layer="DIM",
        style="DIM-100",
        measurement=100,
        text_override="OLD",
        text_position=Point3D(x=x, y=5),
        default_text_position=Point3D(x=x, y=0),
        dimension_line_point=Point3D(x=x, y=10),
        first_extension_origin=Point3D(x=x, y=0),
        second_extension_origin=Point3D(x=x + 10, y=0),
        first_extension_suppressed=suppressed1,
        second_extension_suppressed=suppressed2,
        first_extension_length=5,
        second_extension_length=6,
        dimscale=100,
        ltscale=2,
        object_scale=50,
    )


def approved():
    return Approval(approved=True, fingerprint="sha256:test")


def test_lt_thaws_all_non_xref_layers_without_turning_them_on():
    plan = plan_all_layers_thaw(
        AllLayerStateRequest(document_id="D"),
        [layer("A", is_on=False, is_frozen=True), layer("X|B", is_frozen=True, is_xref=True)],
    )
    assert len(plan.on_freeze_changes) == 1
    assert not plan.on_freeze_changes[0].replacement_on
    assert not plan.on_freeze_changes[0].replacement_frozen


def test_ltg_toggles_on_off_but_keeps_current_layer_on_by_policy():
    plan = plan_toggle_layer_on_off(
        AllLayerStateRequest(document_id="D"),
        [layer("0", is_current=True), layer("A", is_on=True), layer("B", is_on=False)],
    )
    assert [(c.layer, c.replacement_on) for c in plan.on_freeze_changes] == [("A", False), ("B", True)]


def test_ltg_can_error_if_toggle_would_turn_off_current_layer():
    with pytest.raises(ValueError, match="current"):
        plan_toggle_layer_on_off(
            AllLayerStateRequest(document_id="D", current_layer_policy="error"),
            [layer("0", is_current=True)],
        )


def test_lu_unlocks_only_layers_referenced_by_selected_entities():
    plan = plan_selected_layers_unlock(
        SelectedLayerUnlockRequest(document_id="D", selected_entity_handles=("A",)),
        [layer("LOCK", is_locked=True), layer("OTHER", is_locked=True)],
        [LayerEntitySnapshot(handle="A", layer="LOCK", color_index=256, linetype="ByLayer")],
    )
    assert [c.layer for c in plan.lock_changes] == ["LOCK"]


def test_luk_unlocks_all_non_xref_layers():
    plan = plan_all_layers_unlock(
        AllLayerStateRequest(document_id="D"),
        [layer("A", is_locked=True), layer("X|B", is_locked=True, is_xref=True)],
    )
    assert [c.layer for c in plan.lock_changes] == ["A"]


def test_cde_prefixes_measurement_token_and_can_reset_override():
    prefixed = plan_dimension_text_edit(
        DimensionTextEditRequest(document_id="D", target_handles=("A",),
                                 mode=DimensionTextMode.PREFIX_MEASUREMENT, text="≈"),
        [dimension("A")],
    )
    reset = plan_dimension_text_edit(
        DimensionTextEditRequest(document_id="D", target_handles=("A",),
                                 mode=DimensionTextMode.RESET_TO_MEASUREMENT),
        [dimension("A")],
    )
    assert prefixed.changes[0].replacement_override == "≈<>"
    assert reset.changes[0].replacement_override == ""


def test_dcv_rotated_requires_angle_and_preserves_explicit_policies():
    with pytest.raises(ValueError, match="rotation"):
        DimensionConvertRequest(document_id="D", target_handles=("A",), target_kind=LinearDimensionKind.ROTATED,
                                source_disposition=DimensionSourceDisposition.REPLACE,
                                preserve_text_override=True, preserve_style=True)
    plan = plan_dimension_convert(
        DimensionConvertRequest(document_id="D", target_handles=("A",), target_kind=LinearDimensionKind.ROTATED,
            rotation_degrees=90, source_disposition=DimensionSourceDisposition.PRESERVE,
            preserve_text_override=False, preserve_style=True),
        [dimension("A", kind=DimensionKind.ANGULAR)],
    )
    assert plan.creates[0].rotation_degrees == 90
    assert not plan.creates[0].erase_source
    assert plan.creates[0].text_override == ""


def test_ddt_toggles_exact_selected_extension_line():
    plan = plan_dimension_extension_toggle(
        DimensionExtensionToggleRequest(document_id="D", target_handles=("A",),
            target=ExtensionLineTarget.FIRST, operation=SuppressionOperation.TOGGLE),
        [dimension("A", suppressed1=False, suppressed2=True)],
    )
    change = plan.changes[0]
    assert change.replacement_first and change.replacement_second


def test_de_recovered_gap_sources_are_explicit_and_scaled():
    request = ContinueDimensionRequest(
        document_id="D", source_handle="A", continuation_points=(Point3D(x=20, y=0),),
        gap_source=ContinueGapSource.EXPLICIT_DIM_SCALE_FACTOR, explicit_gap_factor=0.2,
        repeat_after_input=True,
    )
    plan = plan_continue_dimension(request, [dimension("A")])
    assert plan.creates[0].gap == 20
    assert plan.repeat_after_input


def test_de_rejects_non_linear_source():
    with pytest.raises(ValueError, match="linear"):
        plan_continue_dimension(
            ContinueDimensionRequest(document_id="D", source_handle="A",
                continuation_points=(Point3D(x=1, y=1),), gap_source=ContinueGapSource.SCREEN_DISTANCE,
                screen_distance=5),
            [dimension("A", kind=DimensionKind.RADIAL)],
        )


def test_dg_recovered_scale_basis_and_baseline_side_drive_points():
    plan = plan_dimension_gap(
        DimensionGapRequest(document_id="D", ordered_handles=("A", "B"), gap_factor=3,
            scale_basis=DimensionScaleBasis.LINE_SCALE, baseline_side=BaselineSide.INSIDE,
            unit_offset_direction=Point3D(x=0, y=1)),
        [dimension("A", x=0), dimension("B", x=10)],
    )
    assert plan.moves[0].replacement_point == Point3D(x=0, y=10, z=0)
    assert plan.moves[1].replacement_point == Point3D(x=0, y=16, z=0)


def test_dg_requires_normalized_direction():
    with pytest.raises(ValueError, match="normalized"):
        DimensionGapRequest(document_id="D", ordered_handles=("A", "B"), gap_factor=1,
            scale_basis=DimensionScaleBasis.OBJECT_SCALE, baseline_side=BaselineSide.OUTSIDE,
            unit_offset_direction=Point3D(x=2, y=0))


def test_dh_returns_text_to_supplied_default_position_and_optionally_resets_override():
    plan = plan_dimension_text_home(
        DimensionTextHomeRequest(document_id="D", target_handles=("A",), reset_text_override=True),
        [dimension("A", x=4)],
    )
    assert plan.changes[0].replacement_position == Point3D(x=4, y=0, z=0)
    assert plan.changes[0].replacement_override == ""


def test_dla_requires_alignment_points_for_selected_sides():
    with pytest.raises(ValueError, match="second"):
        ExtensionArrangeRequest(document_id="D", target_handles=("A",), target=ExtensionLineTarget.BOTH,
                                first_alignment_point=Point3D(x=0, y=0))
    plan = plan_extension_arrange(
        ExtensionArrangeRequest(document_id="D", target_handles=("A",), target=ExtensionLineTarget.SECOND,
                                second_alignment_point=Point3D(x=9, y=9)),
        [dimension("A")],
    )
    assert plan.changes[0].replacement_second == Point3D(x=9, y=9, z=0)


def test_dll_scales_only_selected_extension_lengths():
    plan = plan_extension_length(
        ExtensionLengthRequest(document_id="D", target_handles=("A",), target=ExtensionLineTarget.FIRST,
                               length_factor=2, scale_basis=DimensionScaleBasis.OBJECT_SCALE),
        [dimension("A")],
    )
    assert plan.changes[0].replacement_first == 100
    assert plan.changes[0].replacement_second == 6


def test_locked_dimension_is_rejected():
    locked = dimension("A").model_copy(update={"locked_layer": True})
    with pytest.raises(ValueError, match="cannot be mutated"):
        plan_dimension_text_home(DimensionTextHomeRequest(document_id="D", target_handles=("A",)), [locked])


def test_live_mode_requires_fingerprinted_approval():
    with pytest.raises(ValueError, match="approval"):
        AllLayerStateRequest(document_id="D", dry_run=False)
    assert AllLayerStateRequest(document_id="D", dry_run=False, approval=approved()).approval.approved


class FakeMCP:
    def __init__(self):
        self.tools = []

    def tool(self, *, name, annotations):
        self.tools.append((name, annotations))

        def decorate(function):
            return function

        return decorate


def test_batch11_registers_twelve_read_only_fastmcp_planners():
    mcp = FakeMCP()
    register_headless_core_batch11_tools(mcp)
    assert [name for name, _ in mcp.tools] == [
        "xicad_plan_lt", "xicad_plan_ltg", "xicad_plan_lu", "xicad_plan_luk",
        "xicad_plan_cde", "xicad_plan_dcv", "xicad_plan_ddt", "xicad_plan_de",
        "xicad_plan_dg", "xicad_plan_dh", "xicad_plan_dla", "xicad_plan_dll",
    ]
    assert all(annotation.readOnlyHint for _, annotation in mcp.tools)
