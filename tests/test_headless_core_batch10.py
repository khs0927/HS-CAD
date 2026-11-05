import pytest

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch9 import (
    EntityPropertyPolicy,
    LayerEntitySnapshot,
    LayerSnapshot,
    TargetLayerMode,
    TargetLayerSpec,
)
from xicad_mcp.headless_core_batch10 import (
    ActivateLayersRequest,
    ChangeLayerOnlyRequest,
    ColorLayerBatchMethod,
    ColorLayerCarrier,
    ColorLayerMapping,
    ColorLayerObjectSnapshot,
    ColorLayerStateRequest,
    ColorSource,
    ColorToLayerBatchRequest,
    LayerListDestination,
    LayerListRequest,
    LayerListSort,
    LayerPropertyMode,
    LayerPropertyPatch,
    LayerPropertyRequest,
    LayerSetRequest,
    ObjectKind,
    SimilarityPolicy,
    SimilarLayerObjectSnapshot,
    SimilarObjectsLayerRequest,
    plan_activate_layers,
    plan_change_layer_only,
    plan_color_layer_state,
    plan_color_to_layer_batch,
    plan_layer_list,
    plan_layer_property,
    plan_layer_protection,
    plan_similar_objects_layer,
    register_headless_core_batch10_tools,
)


def layer(name: str, **kwargs):
    return LayerSnapshot(name=name, color_index=7, linetype="Continuous", **kwargs)


def entity(handle: str, layer_name: str, *, color=256, nested=False):
    return LayerEntitySnapshot(handle=handle, layer=layer_name, color_index=color,
                               linetype="ByLayer", nested=nested)


def approved():
    return Approval(approved=True, fingerprint="sha256:test")


def test_lcd_color_number_mode_generates_layers_and_bylayer_changes():
    objects = [ColorLayerObjectSnapshot(handle="A", layer="0", color_index=3, linetype="Continuous")]
    plan = plan_color_to_layer_batch(
        ColorToLayerBatchRequest(document_id="D", method=ColorLayerBatchMethod.COLOR_NUMBER_LAYER_CREATION),
        [layer("0", is_current=True)], objects,
    )
    assert plan.create_layers[0].name == "COLOR_3"
    assert plan.changes[0].replacement_color_index == 256


def test_lcd_recovered_text_override_takes_precedence_over_color_mapping():
    request = ColorToLayerBatchRequest(
        document_id="D", method=ColorLayerBatchMethod.INDIVIDUAL_MAPPING,
        mappings=(ColorLayerMapping(source_color_index=3,
            target_layer=TargetLayerSpec(mode=TargetLayerMode.EXISTING, name="COLOR")),),
        text_override=TargetLayerSpec(mode=TargetLayerMode.EXISTING, name="TEXT"),
    )
    objects = [ColorLayerObjectSnapshot(handle="A", layer="0", color_index=3,
        linetype="ByLayer", carrier=ColorLayerCarrier.TEXT)]
    plan = plan_color_to_layer_batch(request, [layer("COLOR"), layer("TEXT")], objects)
    assert plan.changes[0].replacement_layer == "TEXT"


def test_lcd_mapping_mode_requires_normalized_mapping():
    with pytest.raises(ValueError, match="requires"):
        ColorToLayerBatchRequest(document_id="D", method=ColorLayerBatchMethod.NORMALIZED_LIST_MAPPING)


def test_lco_preserves_color_and_linetype():
    plan = plan_change_layer_only(
        ChangeLayerOnlyRequest(document_id="D", target_handles=("A",), target_layer="NEW"),
        [layer("NEW")],
        [LayerEntitySnapshot(handle="A", layer="OLD", color_index=4, linetype="Dashed")],
    )
    assert plan.command_alias == "LCO"
    assert plan.changes[0].replacement_color_index == 4
    assert plan.changes[0].replacement_linetype == "Dashed"


def test_lcs_requires_explicit_similarity_and_matches_object_kind_and_layer():
    objects = [
        SimilarLayerObjectSnapshot(handle="A", layer="OLD", color_index=256, linetype="ByLayer", object_kind=ObjectKind.LINE),
        SimilarLayerObjectSnapshot(handle="B", layer="OLD", color_index=256, linetype="ByLayer", object_kind=ObjectKind.LINE),
        SimilarLayerObjectSnapshot(handle="C", layer="OTHER", color_index=256, linetype="ByLayer", object_kind=ObjectKind.LINE),
    ]
    plan = plan_similar_objects_layer(
        SimilarObjectsLayerRequest(document_id="D", reference_handle="A",
            similarity_policy=SimilarityPolicy.OBJECT_KIND_AND_LAYER, target_layer="NEW",
            property_policy=EntityPropertyPolicy.BY_LAYER),
        [layer("NEW")], objects,
    )
    assert plan.matched_handles == ("A", "B")


def test_lcs_block_name_policy_requires_block_name():
    with pytest.raises(ValueError, match="block reference"):
        plan_similar_objects_layer(
            SimilarObjectsLayerRequest(document_id="D", reference_handle="A",
                similarity_policy=SimilarityPolicy.BLOCK_NAME, target_layer="NEW",
                property_policy=EntityPropertyPolicy.PRESERVE),
            [layer("NEW")],
            [SimilarLayerObjectSnapshot(handle="A", layer="OLD", color_index=256,
                linetype="ByLayer", object_kind=ObjectKind.LINE)],
        )


def test_lf_freezes_selected_layer_and_rejects_current_layer():
    plan = plan_layer_protection(
        LayerSetRequest(document_id="D", selected_entity_handles=("A",)),
        [layer("0", is_current=True), layer("WALL")], [entity("A", "WALL")], alias="LF",
    )
    assert plan.changes[0].replacement_frozen
    with pytest.raises(ValueError, match="current"):
        plan_layer_protection(
            LayerSetRequest(document_id="D", selected_entity_handles=("A",)),
            [layer("0", is_current=True)], [entity("A", "0")], alias="LF",
        )


def test_lff_freezes_all_except_selected_and_current():
    plan = plan_layer_protection(
        LayerSetRequest(document_id="D", selected_entity_handles=("A",)),
        [layer("0", is_current=True), layer("KEEP"), layer("FREEZE")],
        [entity("A", "KEEP")], alias="LFF",
    )
    assert [(c.layer, c.replacement_frozen) for c in plan.changes] == [("FREEZE", True)]


def test_lfk_and_lk_have_opposite_lock_sets():
    layers = [layer("A"), layer("B")]
    entities = [entity("1", "A")]
    except_selected = plan_layer_protection(LayerSetRequest(document_id="D", selected_entity_handles=("1",)),
                                             layers, entities, alias="LFK")
    selected = plan_layer_protection(LayerSetRequest(document_id="D", selected_entity_handles=("1",)),
                                     layers, entities, alias="LK")
    assert [c.layer for c in except_selected.changes] == ["B"]
    assert [c.layer for c in selected.changes] == ["A"]


def test_llc_can_resolve_colors_from_entity_color_and_turn_matching_layer_off():
    plan = plan_color_layer_state(
        ColorLayerStateRequest(document_id="D", color_indices=(3,), color_source=ColorSource.ENTITY_COLOR),
        [layer("0", is_current=True), layer("MATCH")], [entity("A", "MATCH", color=3)], alias="LLC",
    )
    assert plan.matched_layers == ("MATCH",)
    assert plan.changes[0].replacement_on is False


def test_loc_keeps_current_layer_on_even_when_color_does_not_match():
    plan = plan_color_layer_state(
        ColorLayerStateRequest(document_id="D", color_indices=(3,), color_source=ColorSource.LAYER_COLOR),
        [layer("0", is_current=True), LayerSnapshot(name="MATCH", color_index=3, linetype="Continuous")],
        [], alias="LOC",
    )
    assert plan.matched_layers == ("MATCH",)
    assert not any(change.layer == "0" for change in plan.changes)


def test_los_independently_activates_recovered_off_frozen_locked_properties():
    plan = plan_activate_layers(
        ActivateLayersRequest(document_id="D", target_layers=("A",), turn_on=True, thaw=True, unlock=False),
        [layer("A", is_on=False, is_frozen=True, is_locked=True)],
    )
    change = plan.changes[0]
    assert change.replacement_on and not change.replacement_frozen and change.replacement_locked


def test_los_requires_at_least_one_activation_property():
    with pytest.raises(ValueError, match="at least one"):
        ActivateLayersRequest(document_id="D", target_layers=("A",), turn_on=False, thaw=False, unlock=False)


def test_lp_layer_patch_cannot_freeze_current_layer():
    request = LayerPropertyRequest(document_id="D", target_layers=("0",),
        patch=LayerPropertyPatch(is_frozen=True), mode=LayerPropertyMode.LAYER_ONLY)
    with pytest.raises(ValueError, match="current"):
        plan_layer_property(request, [layer("0", is_current=True)], [])


def test_lp_to_bylayer_and_from_bylayer_are_explicit():
    layers = [LayerSnapshot(name="A", color_index=5, linetype="Dashed")]
    to_plan = plan_layer_property(
        LayerPropertyRequest(document_id="D", target_layers=("A",), mode=LayerPropertyMode.TO_BY_LAYER,
                             change_entity_color=True, change_entity_linetype=True),
        layers, [LayerEntitySnapshot(handle="1", layer="A", color_index=2, linetype="Continuous")],
    )
    from_plan = plan_layer_property(
        LayerPropertyRequest(document_id="D", target_layers=("A",), mode=LayerPropertyMode.FROM_BY_LAYER,
                             change_entity_color=True, change_entity_linetype=True),
        layers, [entity("1", "A")],
    )
    assert to_plan.entity_changes[0].replacement_color_index == 256
    assert from_plan.entity_changes[0].replacement_color_index == 5
    assert from_plan.entity_changes[0].replacement_linetype == "Dashed"


def test_lp_purge_requires_explicit_merge_target():
    with pytest.raises(ValueError, match="requires"):
        LayerPropertyRequest(document_id="D", target_layers=("A",), mode=LayerPropertyMode.LAYER_ONLY,
                             patch=LayerPropertyPatch(is_on=False), purge_after_merge=True)


def test_lst_return_only_is_sorted_cad_free_output():
    plan = plan_layer_list(
        LayerListRequest(document_id="D", destination=LayerListDestination.RETURN_ONLY,
                         sort=LayerListSort.NAME, include_properties=False),
        [layer("B"), layer("a"), layer("X|Y", is_xref=True)],
    )
    assert plan.rendered_lines == ("a", "B")
    assert plan.insertion_point is None


def test_lst_drawing_destination_requires_point_and_approval_for_live_mode():
    with pytest.raises(ValueError, match="insertion_point"):
        LayerListRequest(document_id="D", destination=LayerListDestination.TEXT)
    request = LayerListRequest(document_id="D", destination=LayerListDestination.TABLE,
                               insertion_point=Point3D(x=0, y=0), dry_run=False, approval=approved())
    assert request.approval.approved


class FakeMCP:
    def __init__(self):
        self.tools = []

    def tool(self, *, name, annotations):
        self.tools.append((name, annotations))

        def decorate(function):
            return function

        return decorate


def test_batch10_registers_twelve_read_only_fastmcp_planners():
    mcp = FakeMCP()
    register_headless_core_batch10_tools(mcp)
    assert [name for name, _ in mcp.tools] == [
        "xicad_plan_lcd", "xicad_plan_lco", "xicad_plan_lcs", "xicad_plan_lf",
        "xicad_plan_lff", "xicad_plan_lfk", "xicad_plan_lk", "xicad_plan_llc",
        "xicad_plan_loc", "xicad_plan_los", "xicad_plan_lp", "xicad_plan_lst",
    ]
    assert all(annotation.readOnlyHint for _, annotation in mcp.tools)
