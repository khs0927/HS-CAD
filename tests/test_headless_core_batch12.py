import pytest

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch11 import DimensionKind, DimensionSnapshot
from xicad_mcp.headless_core_batch12 import (
    DimensionChainMode,
    DimensionScaleRequest,
    DimensionScaleScope,
    DimensionStyleEditRequest,
    DimensionStyleMergeRequest,
    DimensionStylePatch,
    DimensionStyleSnapshot,
    DimensionSupplementRequest,
    DimensionTextMoveDirection,
    DimensionTextMoveRequest,
    DimensionUpdateRequest,
    EditDimensionScaleRequest,
    EditScaleMode,
    IntersectionLengthRecord,
    IntersectionLengthRequest,
    IntersectionOutput,
    LeaderAlignAxis,
    LeaderAlignRequest,
    LeaderArrowKind,
    LeaderKind,
    LeaderSnapshot,
    LeaderStyleAction,
    LeaderStyleEditRequest,
    LeaderStylePatch,
    LeaderTextPosition,
    LinearOrientation,
    PolylineDimensionRequest,
    PolylineDimensionSnapshot,
    PolylineVertexPolicy,
    QuickDimensionRequest,
    QuickDimensionSource,
    SupplementalTextPlacement,
    TextCollisionGroup,
    plan_dimension_scale,
    plan_dimension_style_edit,
    plan_dimension_style_merge,
    plan_dimension_supplement,
    plan_dimension_text_move,
    plan_dimension_update,
    plan_edit_dimension_scale,
    plan_intersection_length,
    plan_leader_align,
    plan_leader_style_edit,
    plan_polyline_dimensions,
    plan_quick_dimensions,
    register_headless_core_batch12_tools,
)


def dimension(handle: str, *, style="OLD", scale=100, x=0):
    return DimensionSnapshot(handle=handle, kind=DimensionKind.ALIGNED, layer="DIM", style=style,
        measurement=100, text_override="OLD", text_position=Point3D(x=x, y=5),
        default_text_position=Point3D(x=x, y=0), dimension_line_point=Point3D(x=x, y=10),
        first_extension_origin=Point3D(x=x, y=0), second_extension_origin=Point3D(x=x + 10, y=0),
        first_extension_length=5, second_extension_length=5, dimscale=scale, ltscale=1, object_scale=50)


def style(name: str):
    return DimensionStyleSnapshot(name=name, dimscale=100, text_style="Standard", text_height=2.5,
        arrow_size=2.5, extension_offset=1, baseline_spacing=7, decimal_places=0)


def approved():
    return Approval(approved=True, fingerprint="sha256:test")


def test_dpl_builds_consecutive_dimensions_and_optional_closing_segment():
    polyline = PolylineDimensionSnapshot(handle="P", vertices=(Point3D(x=0,y=0), Point3D(x=10,y=0), Point3D(x=10,y=5)), closed=True)
    plan = plan_polyline_dimensions(PolylineDimensionRequest(document_id="D", source_handle="P",
        vertex_policy=PolylineVertexPolicy.CONSECUTIVE_SEGMENTS, orientation=LinearOrientation.ALIGNED,
        dimension_line_point=Point3D(x=0,y=20), style="DIM", include_closing_segment=True), [polyline])
    assert len(plan.creates) == 3


def test_dpl_explicit_pairs_validate_indices():
    with pytest.raises(ValueError, match="invalid"):
        plan_polyline_dimensions(PolylineDimensionRequest(document_id="D", source_handle="P",
            vertex_policy=PolylineVertexPolicy.EXPLICIT_PAIRS, explicit_pairs=((0,3),),
            orientation=LinearOrientation.ALIGNED, dimension_line_point=Point3D(x=0,y=1), style="DIM"),
            [PolylineDimensionSnapshot(handle="P", vertices=(Point3D(x=0,y=0), Point3D(x=1,y=0)))])


def test_dq_chain_deduplicates_and_sorts_horizontal_points():
    plan = plan_quick_dimensions(QuickDimensionRequest(document_id="D", source_handles=("A","B"),
        chain_mode=DimensionChainMode.CHAIN, orientation=LinearOrientation.HORIZONTAL,
        dimension_line_point=Point3D(x=0,y=10), style="DIM"), [
            QuickDimensionSource(handle="A", points=(Point3D(x=10,y=0),Point3D(x=0,y=0))),
            QuickDimensionSource(handle="B", points=(Point3D(x=10,y=0),Point3D(x=20,y=0)))])
    assert [(c.first_point.x,c.second_point.x) for c in plan.creates] == [(0,10),(10,20)]


def test_dsc_requires_explicit_scope():
    with pytest.raises(ValueError, match="current_style"):
        DimensionScaleRequest(document_id="D", scope=DimensionScaleScope.CURRENT_STYLE, scale=50)
    plan = plan_dimension_scale(DimensionScaleRequest(document_id="D", scope=DimensionScaleScope.SELECTED_DIMENSIONS,
        scale=50, target_handles=("A",)), [dimension("A")])
    assert plan.entity_changes[0].replacement_scale == 50


def test_dse_requires_nonempty_patch_and_existing_style():
    with pytest.raises(ValueError, match="at least one"):
        DimensionStylePatch()
    plan = plan_dimension_style_edit(DimensionStyleEditRequest(document_id="D", target_style="DIM",
        patch=DimensionStylePatch(text_height=3)), [style("DIM")])
    assert plan.patch.text_height == 3


def test_dsm_recovered_nested_and_remove_policy_is_safe():
    request = DimensionStyleMergeRequest(document_id="D", source_styles=("OLD",), target_style="NEW",
                                          include_nested=False, remove_source_styles=True)
    with pytest.raises(ValueError, match="nested"):
        plan_dimension_style_merge(request, [style("OLD"),style("NEW")], [dimension("A")], ("A",))
    plan = plan_dimension_style_merge(request.model_copy(update={"include_nested":True}),
                                      [style("OLD"),style("NEW")], [dimension("A")], ("A",))
    assert plan.remove_styles == ("OLD",)


def test_dtm_moves_collision_group_by_scaled_offsets():
    plan = plan_dimension_text_move(DimensionTextMoveRequest(document_id="D",
        collision_groups=(TextCollisionGroup(handles=("A","B")),), direction=DimensionTextMoveDirection.SIDE,
        offset_factor=.1, unit_direction=Point3D(x=1,y=0)), [dimension("A"),dimension("B",x=5)])
    assert plan.changes[1].replacement_position.x == 15


def test_dto_above_uses_explicit_dimension_stack_separator():
    plan = plan_dimension_supplement(DimensionSupplementRequest(document_id="D", target_handles=("A",),
        text="NOTE", placement=SupplementalTextPlacement.ABOVE), [dimension("A")])
    assert plan.changes[0].replacement_override == "NOTE\\X<>"


def test_du_updates_style_with_preservation_policies():
    plan = plan_dimension_update(DimensionUpdateRequest(document_id="D", target_handles=("A",),
        target_style="NEW", preserve_text_override=True, preserve_text_position=False),
        [style("NEW")], [dimension("A")])
    assert plan.changes[0].replacement_style == "NEW"
    assert not plan.preserve_text_position


def test_ed_recovered_fixed_multiplier_match_and_dsc_modes():
    fixed = plan_edit_dimension_scale(EditDimensionScaleRequest(document_id="D", target_handles=("A",),
        mode=EditScaleMode.FIXED, fixed_scale=25), [dimension("A")])
    multiple = plan_edit_dimension_scale(EditDimensionScaleRequest(document_id="D", target_handles=("A",),
        mode=EditScaleMode.MULTIPLIER, multiplier=2), [dimension("A")])
    matched = plan_edit_dimension_scale(EditDimensionScaleRequest(document_id="D", target_handles=("A",),
        mode=EditScaleMode.MATCH_OBJECT, match_handle="B"), [dimension("A"),dimension("B",scale=30)])
    assert [fixed.changes[0].replacement_scale, multiple.changes[0].replacement_scale,
            matched.changes[0].replacement_scale] == [25,200,30]


def test_il_return_only_computes_normalized_intersection_length():
    plan = plan_intersection_length(IntersectionLengthRequest(document_id="D", records=(
        IntersectionLengthRecord(source_handle="L", first_intersection=Point3D(x=0,y=0),
                                 second_intersection=Point3D(x=3,y=4)),), output=IntersectionOutput.RETURN_ONLY))
    assert plan.results[0].length == 5
    assert plan.dimensions == ()


def test_il_drawing_outputs_require_destination_data():
    with pytest.raises(ValueError, match="line point"):
        IntersectionLengthRequest(document_id="D", records=(IntersectionLengthRecord(source_handle="L",
            first_intersection=Point3D(x=0,y=0), second_intersection=Point3D(x=1,y=0)),),
            output=IntersectionOutput.DIMENSION)


def leader(handle: str, *, x=0, kind=LeaderKind.MLEADER):
    return LeaderSnapshot(handle=handle, kind=kind, style="OLD", start_point=Point3D(x=0,y=0),
                          end_point=Point3D(x=x,y=5))


def test_lda_aligns_endpoint_to_axis_and_explicit_line():
    axis = plan_leader_align(LeaderAlignRequest(document_id="D", target_handles=("A",),
        axis=LeaderAlignAxis.X, coordinate=10), [leader("A",x=2)])
    line = plan_leader_align(LeaderAlignRequest(document_id="D", target_handles=("A",),
        axis=LeaderAlignAxis.EXPLICIT_LINE, line_start=Point3D(x=0,y=0), line_end=Point3D(x=10,y=0)),
        [leader("A",x=2)])
    assert axis.changes[0].replacement_point.x == 10
    assert line.changes[0].replacement_point.y == 0


def test_lse_recovered_style_patch_is_complete_and_kind_checked():
    patch = LeaderStylePatch(scale=100, arrow_kind=LeaderArrowKind.CIRCLE,
        text_position=LeaderTextPosition.TOP, text_style="Standard", arrow_size=2,
        text_gap=1, text_size=2.5, dogleg_length=5, text_color_index=7, leader_color_index=7)
    plan = plan_leader_style_edit(LeaderStyleEditRequest(document_id="D", leader_kind=LeaderKind.MLEADER,
        action=LeaderStyleAction.SAVE_NEW, target_style="NEW", patch=patch), [])
    assert plan.patch.arrow_kind is LeaderArrowKind.CIRCLE
    with pytest.raises(ValueError, match="wrong kind"):
        plan_leader_style_edit(LeaderStyleEditRequest(document_id="D", target_handles=("A",),
            leader_kind=LeaderKind.LEADER, action=LeaderStyleAction.APPLY_EXISTING,
            source_style="OLD", target_style="NEW"), [leader("A")])


def test_live_mode_requires_fingerprinted_approval():
    with pytest.raises(ValueError, match="approval"):
        DimensionUpdateRequest(document_id="D", target_handles=("A",), target_style="NEW", dry_run=False)
    assert DimensionUpdateRequest(document_id="D", target_handles=("A",), target_style="NEW",
                                  dry_run=False, approval=approved()).approval.approved


class FakeMCP:
    def __init__(self): self.tools=[]
    def tool(self, *, name, annotations):
        self.tools.append((name,annotations))
        return lambda function:function


def test_batch12_registers_twelve_read_only_fastmcp_planners():
    mcp=FakeMCP()
    register_headless_core_batch12_tools(mcp)
    assert [name for name,_ in mcp.tools] == ["xicad_plan_dpl","xicad_plan_dq","xicad_plan_dsc",
        "xicad_plan_dse","xicad_plan_dsm","xicad_plan_dtm","xicad_plan_dto","xicad_plan_du",
        "xicad_plan_ed","xicad_plan_il","xicad_plan_lda","xicad_plan_lse"]
    assert all(a.readOnlyHint for _,a in mcp.tools)
