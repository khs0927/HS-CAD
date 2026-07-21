import asyncio
from datetime import date

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch14 import GeometrySnapshot
from xicad_mcp.headless_core_batch15 import (
    ClosePolicy,
    CommandEditRequest,
    ConflictPolicy,
    ContentKind,
    ContentSnapshot,
    CopyContentsRequest,
    DateStampRequest,
    DefinitionKind,
    DocumentSnapshot,
    ExplorerRequest,
    FlattenRequest,
    FrameSize,
    GroupEditRequest,
    GroupOperation,
    GroupSnapshot,
    LayerCreateSpec,
    OpenDrawingRequest,
    QuickQuitRequest,
    ShortcutChange,
    ShortcutOperation,
    ShortcutSection,
    StartRequest,
    StealItem,
    StealRequest,
    SteelKind,
    SteelRequest,
    SteelView,
    plan_command_edit,
    plan_copy_contents,
    plan_date_stamp,
    plan_explorer,
    plan_flatten,
    plan_group_edit,
    plan_open_drawing,
    plan_quick_quit,
    plan_start,
    plan_steal,
    plan_steel,
    register_headless_core_batch15_tools,
)


def test_ct_copies_only_matching_content_kind() -> None:
    snapshots = (
        ContentSnapshot(handle="S", kind=ContentKind.TEXT, value="ABC"),
        ContentSnapshot(handle="T", kind=ContentKind.TEXT, value="old"),
    )
    plan = plan_copy_contents(
        CopyContentsRequest(
            document_id="D",
            source_handle="S",
            target_handles=("T",),
            expected_kind=ContentKind.TEXT,
        ),
        snapshots,
    )
    assert plan.changes == {"T": "ABC"}


def test_dts_uses_caller_supplied_date() -> None:
    plan = plan_date_stamp(
        DateStampRequest(
            document_id="D",
            creation_date=date(2026, 7, 21),
            insertion_point=Point3D(x=1, y=2),
            format_template="%Y-%m-%d",
            prefix="CREATED: ",
            layer="TXT",
            text_style="Standard",
            text_height=2.5,
        )
    )
    assert plan.create.text == "CREATED: 2026-07-21"


def test_flt_sets_all_vertex_z_values() -> None:
    snapshot = GeometrySnapshot(
        handle="A",
        entity_type="LWPOLYLINE",
        vertices=(Point3D(x=0, y=0, z=3), Point3D(x=1, y=0, z=7)),
        layer="G",
    )
    plan = plan_flatten(
        FlattenRequest(document_id="D", target_handles=("A",), target_z=0),
        (snapshot,),
    )
    assert [point.z for point in plan.target_vertices["A"]] == [0, 0]


def test_flt_blocks_unmodelled_curve_preservation() -> None:
    with pytest.raises(ValueError, match="curve parameters"):
        FlattenRequest(
            document_id="D",
            target_handles=("A",),
            preserve_nonplanar_curves=True,
        )


def test_gee_adds_members_without_duplicates() -> None:
    plan = plan_group_edit(
        GroupEditRequest(
            document_id="D",
            group_name="G",
            operation=GroupOperation.ADD_MEMBERS,
            member_handles=("B", "C"),
        ),
        (GroupSnapshot(name="G", member_handles=("A", "B")),),
    )
    assert plan.resulting_members == ("A", "B", "C")


def test_stl_requires_source_digest_and_explicit_conflict_policy() -> None:
    plan = plan_steal(
        StealRequest(
            document_id="D",
            source_document_path="C:/drawings/source.dwg",
            items=(StealItem(kind=DefinitionKind.LAYER, name="A"),),
            conflict_policy=ConflictPolicy.KEEP_TARGET,
            source_digest="sha256:" + "a" * 64,
        )
    )
    assert plan.source_digest.endswith("a" * 64)


def test_com_blocks_direct_pgp_mutation() -> None:
    change = ShortcutChange(
        operation=ShortcutOperation.UPSERT,
        alias="ZZ",
        command="xiZZ",
        description="test",
        section=ShortcutSection.NONE,
    )
    with pytest.raises(ValueError, match="PGP mutation"):
        CommandEditRequest(
            document_id="D",
            key_file_path="C:/xicad/xiLib/xiShortkey.key",
            expected_file_digest="sha256:" + "b" * 64,
            changes=(change,),
            apply_to_pgp=True,
        )
    plan = plan_command_edit(
        CommandEditRequest(
            document_id="D",
            key_file_path="C:/xicad/xiLib/xiShortkey.key",
            expected_file_digest="sha256:" + "b" * 64,
            changes=(change,),
        )
    )
    assert plan.external_write_blocked


def test_exp_resolves_only_parent_and_blocks_process() -> None:
    plan = plan_explorer(ExplorerRequest(document_id="D", drawing_path="C:/drawings/a.dwg"))
    assert plan.folder_path == "C:\\drawings"
    assert plan.external_process_blocked


def test_ol_uses_explicit_selection_and_read_only_flag() -> None:
    request = OpenDrawingRequest(
        document_id="D",
        current_path="C:/d/a.dwg",
        candidate_paths=("C:/d/a.dwg", "C:/d/b.dwg"),
        selected_path="C:/d/b.dwg",
        read_only=True,
        operation="list_select",
    )
    plan = plan_open_drawing(request)
    assert plan.command_alias == "OL" and plan.read_only


def test_on_selects_next_casefold_sorted_file() -> None:
    request = OpenDrawingRequest(
        document_id="D",
        current_path="C:/d/a.dwg",
        candidate_paths=("C:/d/C.dwg", "C:/d/a.dwg", "C:/d/b.dwg"),
        read_only=False,
        operation="next",
    )
    assert plan_open_drawing(request).target_path == "C:\\d\\b.dwg"


def test_qq_requires_separate_discard_confirmation() -> None:
    with pytest.raises(ValueError, match="confirm_discard"):
        QuickQuitRequest(
            document_id="D",
            target_document_ids=("D",),
            policy=ClosePolicy.DISCARD_ALL,
        )
    plan = plan_quick_quit(
        QuickQuitRequest(
            document_id="D",
            target_document_ids=("D",),
            policy=ClosePolicy.SAVE_MODIFIED,
        ),
        (DocumentSnapshot(document_id="D", path="C:/d/a.dwg", modified=True),),
    )
    assert plan.actions[0].save_before_close and plan.external_close_blocked


def test_stt_recovers_dcl_scale_layer_and_frame_fields() -> None:
    plan = plan_start(
        StartRequest(
            document_id="D",
            drawing_scale=100,
            apply_ltscale=True,
            apply_dimscale=True,
            create_layers=(LayerCreateSpec(name="DIM", color=2, linetype="Continuous"),),
            frame_size=FrameSize.A3,
            frame_file="C:/xicad/A3.dwg",
            insertion_point=Point3D(x=0, y=0),
        )
    )
    assert plan.system_variables == {"LTSCALE": 100, "DIMSCALE": 100}
    assert plan.frame_size is FrameSize.A3


def test_be_requires_length_for_non_section_view() -> None:
    with pytest.raises(ValueError, match="requires length"):
        SteelRequest(
            document_id="D",
            kind=SteelKind.H_BEAM,
            view=SteelView.SIDE,
            insertion_point=Point3D(x=0, y=0),
            depth=300,
            width=150,
            web_thickness=8,
            flange_thickness=12,
            section_layer="S",
            elevation_layer="E",
            hidden_layer="H",
            square_corners=True,
        )


def test_be_outputs_deterministic_outline() -> None:
    plan = plan_steel(
        SteelRequest(
            document_id="D",
            kind=SteelKind.H_BEAM,
            view=SteelView.SECTION,
            insertion_point=Point3D(x=0, y=0),
            depth=300,
            width=150,
            web_thickness=8,
            flange_thickness=12,
            section_layer="S",
            elevation_layer="E",
            hidden_layer="H",
            square_corners=True,
        )
    )
    assert plan.outline[0] == Point3D(x=-75, y=-150, z=0)
    assert plan.semantic_evidence.startswith("xiBeam DCL")


def test_non_dry_request_requires_approval_fingerprint() -> None:
    with pytest.raises(ValueError, match="approval fingerprint"):
        ExplorerRequest(document_id="D", drawing_path="C:/d/a.dwg", dry_run=False)


def test_registers_12_read_only_fastmcp_tools() -> None:
    mcp = FastMCP("batch15-test")
    register_headless_core_batch15_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 12
    assert {tool.name for tool in tools} == {
        "xicad_plan_ct",
        "xicad_plan_dts",
        "xicad_plan_flt",
        "xicad_plan_gee",
        "xicad_plan_stl",
        "xicad_plan_com",
        "xicad_plan_exp",
        "xicad_plan_ol",
        "xicad_plan_on",
        "xicad_plan_qq",
        "xicad_plan_stt",
        "xicad_plan_be",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
