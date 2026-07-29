import pytest

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch5 import TextEntityKind, TextEntitySnapshot
from xicad_mcp.headless_core_batch11 import DimensionKind, DimensionSnapshot
from xicad_mcp.headless_core_batch12 import LeaderKind
from xicad_mcp.headless_core_batch13 import (
    AutoLeaderRequest,
    BreakSymbolKind,
    BreakSymbolRequest,
    CloudStyle,
    CloudWidthRequest,
    ContourJoinEnd,
    ContourJoinRequest,
    DirectionLineRequest,
    DirectionOperation,
    FlattenPolicy,
    JoinPolylineRequest,
    JumpLineRequest,
    JumpRepresentation,
    JumpSide,
    LeaderDefinitionSource,
    LeaderEndShape,
    LeaderPlacement,
    LeaderTextKind,
    LeaderTextLocation,
    Polyline3DConvertRequest,
    PolylineSnapshot,
    ProjectionPolicy,
    ProjectionRequest,
    RevisionCloudRequest,
    SourceDisposition,
    SplitDimensionRequest,
    TextLeaderPlacement,
    TextToLeaderRequest,
    WidthSide,
    plan_3dpoly_to_lwpoly,
    plan_auto_leader,
    plan_cloud_width,
    plan_direction_line,
    plan_join_polylines,
    plan_jump_line,
    plan_projection,
    plan_split_dimension,
    plan_text_to_leader,
    register_headless_core_batch13_tools,
)


def poly(h, vs, **kw):
    return PolylineSnapshot(handle=h, vertices=tuple(vs), closed=False, layer="G", **kw)


def dim():
    return DimensionSnapshot(
        handle="D",
        kind=DimensionKind.ALIGNED,
        layer="DIM",
        style="S",
        measurement=10,
        text_position=Point3D(x=0, y=1),
        default_text_position=Point3D(x=0, y=0),
        dimension_line_point=Point3D(x=0, y=5),
        first_extension_origin=Point3D(x=0, y=0),
        second_extension_origin=Point3D(x=10, y=0),
        first_extension_length=1,
        second_extension_length=1,
        dimscale=1,
        ltscale=1,
        object_scale=1,
    )


def approved():
    return Approval(approved=True, fingerprint="sha256:test")


def test_lx_recovered_dcl_contract():
    r = AutoLeaderRequest(
        document_id="D",
        placements=(
            LeaderPlacement(
                arrow_point=Point3D(x=0, y=0), elbow_point=Point3D(x=1, y=1), text_point=Point3D(x=2, y=1), text="A"
            ),
        ),
        definition_source=LeaderDefinitionSource.XICAD_EXPLICIT,
        style="S",
        layer="L",
        text_kind=LeaderTextKind.MTEXT,
        end_shape=LeaderEndShape.ARROW,
        text_location=LeaderTextLocation.TOP,
        text_style="Standard",
        text_height=2.5,
        head_size=1,
        dimscale=100,
    )
    assert plan_auto_leader(r).creates[0].text == "A"


def test_sd_splits_linear_dimension():
    p = plan_split_dimension(
        SplitDimensionRequest(
            document_id="D",
            source_handle="D",
            split_points=(Point3D(x=4, y=0),),
            source_disposition=SourceDisposition.REPLACE,
        ),
        [dim()],
    )
    assert len(p.segments) == 2 and p.erase_source


def test_tl_links_existing_text_and_style_policy():
    t = TextEntitySnapshot(
        handle="T",
        text="TXT",
        kind=TextEntityKind.TEXT,
        layer="T",
        text_style="S",
        text_height=2.5,
        insertion_point=Point3D(x=2, y=2),
    )
    r = TextToLeaderRequest(
        document_id="D",
        placements=(
            TextLeaderPlacement(text_handle="T", arrow_point=Point3D(x=0, y=0), elbow_point=Point3D(x=1, y=1)),
        ),
        leader_kind=LeaderKind.MLEADER,
        style="LS",
        dimscale=100,
        layer="L",
        end_shape=LeaderEndShape.DOT,
        head_size=1,
        match_text_to_style=True,
        target_text_style="N",
        target_text_height=3,
        preserve_selection_order=True,
        line_gap_height_factor=1,
    )
    assert plan_text_to_leader(r, [t]).text_style_changes["T"] == ("N", 3)


def test_2dp_affine_translation():
    m = ((1, 0, 0, 5), (0, 1, 0, 2), (0, 0, 1, 0), (0, 0, 0, 1))
    r = ProjectionRequest(
        document_id="D",
        source_handles=("A",),
        source_boundary_handle="S",
        target_boundary_handle="T",
        policy=ProjectionPolicy.AFFINE_MATRIX,
        affine_matrix_4x4=m,
        target_layer="X",
        source_disposition=SourceDisposition.PRESERVE,
    )
    p = plan_projection(r, [poly("A", [Point3D(x=0, y=0), Point3D(x=1, y=0)])])
    assert p.creates[0].vertices[0] == Point3D(x=5, y=2, z=0)


def test_3tp_drop_z():
    r = Polyline3DConvertRequest(
        document_id="D",
        target_handles=("A",),
        flatten_policy=FlattenPolicy.DROP_Z,
        source_disposition=SourceDisposition.REPLACE,
    )
    assert (
        plan_3dpoly_to_lwpoly(r, [poly("A", [Point3D(x=0, y=0, z=5), Point3D(x=1, y=0, z=8)])]).creates[0].vertices[1].z
        == 0
    )


def test_boo_checks_endpoint_tolerance():
    r = JoinPolylineRequest(
        document_id="D",
        ordered_handles=("A", "B"),
        tolerance=0.1,
        target_layer="G",
        source_disposition=SourceDisposition.REPLACE,
    )
    p = plan_join_polylines(
        r, [poly("A", [Point3D(x=0, y=0), Point3D(x=1, y=0)]), poly("B", [Point3D(x=1, y=0), Point3D(x=2, y=0)])]
    )
    assert len(p.create.vertices) == 3


def test_bs_requires_distinct_endpoints():
    with pytest.raises(ValueError):
        BreakSymbolRequest(
            document_id="D",
            start=Point3D(x=0, y=0),
            end=Point3D(x=0, y=0),
            kind=BreakSymbolKind.ZIGZAG,
            width=1,
            height=1,
            layer="L",
        )


def test_cbj_requires_boundary_points():
    with pytest.raises(ValueError, match="start"):
        ContourJoinRequest(
            document_id="D",
            contour_handle="C",
            boundary_handle="B",
            ends=ContourJoinEnd.START,
            source_disposition=SourceDisposition.PRESERVE,
        )


def test_cm_validates_arc_range():
    with pytest.raises(ValueError, match="max"):
        RevisionCloudRequest(
            document_id="D",
            boundary_vertices=(Point3D(x=0, y=0), Point3D(x=1, y=0), Point3D(x=1, y=1)),
            min_arc_length=2,
            max_arc_length=1,
            style=CloudStyle.NORMAL,
            layer="C",
        )


def test_cmw_width_spec():
    r = CloudWidthRequest(
        document_id="D",
        target_handles=("C",),
        width=2,
        side=WidthSide.BOTH,
        cap_ends=True,
        source_disposition=SourceDisposition.PRESERVE,
    )
    assert plan_cloud_width(r, [poly("C", [Point3D(x=0, y=0), Point3D(x=1, y=0)])]).specs[0].width == 2


def test_drl_reverse():
    r = DirectionLineRequest(
        document_id="D", target_handles=("A",), operation=DirectionOperation.REVERSE, arrow_size=1, layer="L"
    )
    assert plan_direction_line(r, [poly("A", [Point3D(x=0, y=0), Point3D(x=1, y=0)])]).reversed_vertices["A"][0].x == 1


def test_jul_alternates_jump_side():
    r = JumpLineRequest(
        document_id="D",
        base_handle="A",
        crossing_points=(Point3D(x=1, y=0), Point3D(x=2, y=0)),
        radius=0.5,
        side=JumpSide.ALTERNATE,
        representation=JumpRepresentation.ARC,
        layer="L",
    )
    assert [j.side for j in plan_jump_line(r, [poly("A", [Point3D(x=0, y=0), Point3D(x=3, y=0)])]).jumps] == [
        JumpSide.LEFT,
        JumpSide.RIGHT,
    ]


def test_live_requires_approval():
    with pytest.raises(ValueError, match="approval"):
        CloudWidthRequest(
            document_id="D",
            target_handles=("A",),
            width=1,
            side=WidthSide.LEFT,
            cap_ends=False,
            source_disposition=SourceDisposition.PRESERVE,
            dry_run=False,
        )


class FakeMCP:
    def __init__(self):
        self.tools = []

    def tool(self, *, name, annotations):
        self.tools.append((name, annotations))
        return lambda f: f


def test_registers_12_read_only_tools():
    m = FakeMCP()
    register_headless_core_batch13_tools(m)
    assert len(m.tools) == 12 and all(a.readOnlyHint for _, a in m.tools)
