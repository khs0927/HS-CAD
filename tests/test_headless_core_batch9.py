import pytest

from xicad_mcp.headless_core_batch1 import Approval
from xicad_mcp.headless_core_batch9 import (
    AllLayersOnRequest,
    ChangeLayerRequest,
    ColorToLayerRequest,
    DrawOrderByLayerRequest,
    DrawOrderDirection,
    EntityPropertyPolicy,
    EntityVisibilityRequest,
    EraseLayerRequest,
    LayerEntitySnapshot,
    LayerMergeRequest,
    LayerSnapshot,
    SelectedLayerRequest,
    SetCurrentLayerRequest,
    TargetLayerMode,
    TargetLayerSpec,
    plan_all_layers_on,
    plan_change_layer,
    plan_color_to_layer,
    plan_draw_order_by_layer,
    plan_entity_visibility,
    plan_erase_layer,
    plan_layer_merge,
    plan_selected_layers_isolate,
    plan_selected_layers_off,
    plan_set_current_layer,
    register_headless_core_batch9_tools,
)


def layer(name: str, **kwargs):
    return LayerSnapshot(name=name, color_index=7, linetype="Continuous", **kwargs)


def entity(handle: str, layer_name: str, *, color=256, visible=True, block=None, nested=False):
    return LayerEntitySnapshot(
        handle=handle,
        layer=layer_name,
        color_index=color,
        linetype="ByLayer",
        visible=visible,
        block_name=block,
        nested=nested,
    )


def approved():
    return Approval(approved=True, fingerprint="sha256:test")


def test_alias_1_turns_selected_entity_layers_off():
    plan = plan_selected_layers_off(
        SelectedLayerRequest(document_id="D", selected_entity_handles=("A",)),
        [layer("0", is_current=True), layer("WALL")],
        [entity("A", "WALL")],
    )
    assert [(c.layer, c.replacement_on) for c in plan.changes] == [("WALL", False)]


def test_alias_1_current_layer_policy_is_explicit():
    with pytest.raises(ValueError, match="current"):
        plan_selected_layers_off(
            SelectedLayerRequest(document_id="D", selected_entity_handles=("A",)),
            [layer("0", is_current=True)],
            [entity("A", "0")],
        )


def test_alias_2_isolates_selected_layers_but_keeps_current_layer_on():
    plan = plan_selected_layers_isolate(
        SelectedLayerRequest(document_id="D", selected_entity_handles=("A",)),
        [layer("0", is_current=True), layer("WALL"), layer("TEXT")],
        [entity("A", "WALL")],
    )
    assert [(c.layer, c.replacement_on) for c in plan.changes] == [("TEXT", False)]


def test_alias_3_turns_layers_on_and_only_thaws_when_requested():
    plan = plan_all_layers_on(
        AllLayersOnRequest(document_id="D", thaw_frozen=True),
        [layer("A", is_on=False, is_frozen=True), layer("X|B", is_on=False, is_xref=True)],
    )
    assert len(plan.changes) == 1
    assert plan.changes[0].replacement_on
    assert not plan.changes[0].replacement_frozen


def test_dol_preserves_explicit_layer_rank_and_direction():
    plan = plan_draw_order_by_layer(
        DrawOrderByLayerRequest(
            document_id="D",
            ordered_layers=("TEXT", "WALL"),
            direction=DrawOrderDirection.FIRST_LAYER_TO_FRONT,
        ),
        [entity("W", "WALL"), entity("T", "TEXT")],
    )
    assert plan.ordered_handles == ("T", "W")
    assert plan.direction is DrawOrderDirection.FIRST_LAYER_TO_FRONT


def test_ely_requires_exact_expected_handles_and_protects_layer_zero():
    with pytest.raises(ValueError, match="protected"):
        EraseLayerRequest(document_id="D", target_layers=("0",), expected_entity_handles=("A",))
    request = EraseLayerRequest(document_id="D", target_layers=("OLD",), expected_entity_handles=("A",))
    with pytest.raises(ValueError, match="do not match"):
        plan_erase_layer(request, [layer("OLD")], [entity("A", "OLD"), entity("B", "OLD")])


def test_ely_builds_delete_and_optional_layer_record_plan():
    plan = plan_erase_layer(
        EraseLayerRequest(
            document_id="D",
            target_layers=("OLD",),
            expected_entity_handles=("A",),
            erase_layer_records=True,
        ),
        [layer("OLD")],
        [entity("A", "OLD")],
    )
    assert plan.erase_handles == ("A",)
    assert plan.erase_layer_records == ("OLD",)


def test_eoo_turns_only_hidden_entities_on():
    plan = plan_entity_visibility(
        EntityVisibilityRequest(document_id="D"),
        [entity("A", "L", visible=False), entity("B", "L", visible=True)],
        alias="EOO",
    )
    assert [c.handle for c in plan.changes] == ["A"]


def test_esf_can_include_same_block_name_from_recovered_dcl_option():
    plan = plan_entity_visibility(
        EntityVisibilityRequest(document_id="D", selected_handles=("A",), include_same_block_name=True),
        [entity("A", "L", block="CHAIR"), entity("B", "L", block="CHAIR"), entity("C", "L")],
        alias="ESF",
    )
    assert [c.handle for c in plan.changes] == ["A", "B"]
    assert all(not c.replacement_visible for c in plan.changes)


def test_eso_hides_everything_except_selected_entities():
    plan = plan_entity_visibility(
        EntityVisibilityRequest(document_id="D", selected_handles=("A",)),
        [entity("A", "L"), entity("B", "L")],
        alias="ESO",
    )
    assert [c.handle for c in plan.changes] == ["B"]


def test_ew_sets_current_layer_from_source_entity_and_plans_thaw():
    plan = plan_set_current_layer(
        SetCurrentLayerRequest(document_id="D", source_entity_handle="A", thaw_policy="thaw"),
        [layer("0", is_current=True), layer("WALL", is_frozen=True, is_on=False)],
        [entity("A", "WALL")],
    )
    assert plan.expected_current_layer == "0"
    assert plan.replacement_current_layer == "WALL"
    assert not plan.prerequisite_changes[0].replacement_frozen


def test_lam_applies_recovered_preserve_and_remove_policies():
    plan = plan_layer_merge(
        LayerMergeRequest(
            document_id="D",
            source_layers=("OLD",),
            target_layer="NEW",
            include_nested=False,
            preserve_entity_color=True,
            preserve_entity_linetype=False,
            remove_source_layers=True,
        ),
        [layer("OLD"), layer("NEW")],
        [entity("A", "OLD", color=3)],
    )
    assert [c.handle for c in plan.entity_changes] == ["A"]
    assert plan.entity_changes[0].replacement_color_index == 3
    assert plan.entity_changes[0].replacement_linetype == "ByLayer"
    assert plan.remove_layers == ("OLD",)


def test_lam_protects_current_source_layer():
    with pytest.raises(ValueError, match="cannot be merged"):
        plan_layer_merge(
            LayerMergeRequest(
                document_id="D",
                source_layers=("OLD",),
                target_layer="NEW",
                include_nested=False,
                preserve_entity_color=False,
                preserve_entity_linetype=False,
                remove_source_layers=False,
            ),
            [layer("OLD", is_current=True), layer("NEW")],
            [],
        )


def test_lc_existing_layer_and_property_policies_are_explicit():
    plan = plan_change_layer(
        ChangeLayerRequest(
            document_id="D",
            target_handles=("A",),
            target_layer=TargetLayerSpec(mode=TargetLayerMode.EXISTING, name="NEW"),
            color_policy=EntityPropertyPolicy.BY_LAYER,
            linetype_policy=EntityPropertyPolicy.PRESERVE,
        ),
        [layer("NEW")],
        [entity("A", "OLD", color=2)],
    )
    assert plan.create_layer is None
    assert plan.changes[0].replacement_color_index == 256


def test_lc_create_mode_requires_complete_layer_properties():
    with pytest.raises(ValueError, match="requires"):
        TargetLayerSpec(mode=TargetLayerMode.CREATE, name="NEW")
    plan = plan_change_layer(
        ChangeLayerRequest(
            document_id="D",
            target_handles=("A",),
            target_layer=TargetLayerSpec(mode=TargetLayerMode.CREATE, name="NEW", color_index=4,
                                         linetype="Continuous"),
            color_policy=EntityPropertyPolicy.PRESERVE,
            linetype_policy=EntityPropertyPolicy.PRESERVE,
        ),
        [],
        [entity("A", "OLD")],
    )
    assert plan.create_layer.name == "NEW"


def test_lcc_selects_exact_color_and_resets_color_to_bylayer():
    plan = plan_color_to_layer(
        ColorToLayerRequest(
            document_id="D",
            source_color_indices=(3,),
            target_layer=TargetLayerSpec(mode=TargetLayerMode.EXISTING, name="COLOR3"),
        ),
        [layer("COLOR3")],
        [entity("A", "OLD", color=3), entity("B", "OLD", color=4)],
    )
    assert [c.handle for c in plan.changes] == ["A"]
    assert plan.changes[0].replacement_color_index == 256


def test_live_mode_requires_fingerprinted_approval():
    with pytest.raises(ValueError, match="approval"):
        AllLayersOnRequest(document_id="D", dry_run=False)
    assert AllLayersOnRequest(document_id="D", dry_run=False, approval=approved()).approval.approved


class FakeMCP:
    def __init__(self):
        self.tools = []

    def tool(self, *, name, annotations):
        self.tools.append((name, annotations))

        def decorate(function):
            return function

        return decorate


def test_batch9_registers_twelve_read_only_fastmcp_planners():
    mcp = FakeMCP()
    register_headless_core_batch9_tools(mcp)
    assert [name for name, _ in mcp.tools] == [
        "xicad_plan_1", "xicad_plan_2", "xicad_plan_3", "xicad_plan_dol",
        "xicad_plan_ely", "xicad_plan_eoo", "xicad_plan_esf", "xicad_plan_eso",
        "xicad_plan_ew", "xicad_plan_lam", "xicad_plan_lc", "xicad_plan_lcc",
    ]
    assert all(annotation.readOnlyHint for _, annotation in mcp.tools)
