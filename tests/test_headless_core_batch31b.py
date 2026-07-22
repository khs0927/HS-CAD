from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from xicad_mcp.headless_core_batch1 import Approval
from xicad_mcp.headless_core_batch31b import (
    DrawingFileSnapshot,
    ExactEntityResult,
    ExactGeometryResult,
    GeometrySnapshot,
    KitchenCornerRequest,
    PlaneLevelRequest,
    Point3D,
    ReferenceMarkRequest,
    ResourceSnapshot,
    RoofDrainRequest,
    RubbleRequest,
    SaveAsBlockRequest,
    SaveAsBlockResult,
    SectionSymbolRequest,
    UtilityLineKind,
    UtilityLineRequest,
    plan_kitchen_corner,
    plan_plane_level,
    plan_reference_mark,
    plan_roof_drain,
    plan_rubble,
    plan_save_as_block,
    plan_section_symbol,
    plan_utility_line,
    register_headless_core_batch31b_tools,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def geometry(count: int, revision: str = "g1") -> GeometrySnapshot:
    return GeometrySnapshot(
        revision=revision,
        geometry_digest=DIGEST_A,
        points=tuple(Point3D(x=float(index), y=float(index % 2)) for index in range(count)),
    )


def result(source: GeometrySnapshot, *, layer: str = "SYM") -> ExactGeometryResult:
    return ExactGeometryResult(
        input_revision=source.revision,
        entities=(
            ExactEntityResult(
                result_id="20",
                result_revision="r2",
                entity_type="AcDbPolyline",
                owner="Model",
                layer=layer,
                state_digest=DIGEST_B,
            ),
        ),
        manifest_digest=DIGEST_B,
    )


def resource(path: str) -> ResourceSnapshot:
    return ResourceSnapshot(path=path, revision="f1", content_digest=DIGEST_A)


def test_kcl_preserves_exact_three_points_and_does_not_infer_help_inconsistency() -> None:
    source = geometry(3)
    request = KitchenCornerRequest(
        document_id="D", source=source, refrigerator_width=900, result=result(source)
    )
    plan = plan_kitchen_corner(request)
    assert plan.legacy_symbol == "xiKICL"
    assert any("inconsistently" in gap for gap in plan.semantic_gaps)
    with pytest.raises(ValueError, match="exactly 3"):
        plan_kitchen_corner(request.model_copy(update={"source": geometry(2)}))


def test_plm_binds_dcl_fields_block_revision_and_exact_result() -> None:
    source = geometry(1)
    request = PlaneLevelRequest(
        document_id="D",
        source=source,
        level_text="1,200",
        prefix="F.L ",
        decimals=0,
        text_style="나눔스퀘어",
        text_height=3500,
        symbol_resource=resource("C:/xicad/Lib/xi_Lemark.dwg"),
        result=result(source),
    )
    assert plan_plane_level(request).result == request.result
    with pytest.raises(ValueError, match="input geometry revision"):
        plan_plane_level(request.model_copy(update={"result": result(geometry(1, "old"))}))


def test_ppb_requires_four_ordered_points_and_explicit_style_fields() -> None:
    source = geometry(4)
    request = ReferenceMarkRequest(
        document_id="D",
        source=source,
        detail_number="3",
        reference_drawing="A-201",
        layer="A-SYMB",
        line_type="CONTINUOUS",
        color=7,
        symbol_size=10,
        text_style="Standard",
        text_height=2.5,
        result=result(source),
    )
    assert plan_reference_mark(request).command_alias == "PPB"
    with pytest.raises(ValueError, match="exactly 4"):
        plan_reference_mark(request.model_copy(update={"source": geometry(3)}))


def test_rd_keeps_diameter_and_versioned_block_but_derives_no_geometry() -> None:
    source = geometry(1)
    request = RoofDrainRequest(
        document_id="D",
        source=source,
        diameter=125,
        layer="DRAIN",
        symbol_resource=resource("C:/xicad/Lib/xi_RoofDrain.dwg"),
        result=result(source, layer="DRAIN"),
    )
    assert plan_roof_drain(request).legacy_symbol == "xiRoofDrain"
    with pytest.raises(ValueError):
        RoofDrainRequest.model_validate({**request.model_dump(), "diameter": 0})


def test_rub_requires_two_points_and_caller_selected_resource() -> None:
    source = geometry(2)
    request = RubbleRequest(
        document_id="D",
        source=source,
        symbol_resource=resource("C:/xicad/Lib/xi_Rubble.dwg"),
        result=result(source),
    )
    plan = plan_rubble(request)
    assert any("RUB.dwg" in gap for gap in plan.semantic_gaps)
    with pytest.raises(ValueError, match="exactly 2"):
        plan_rubble(request.model_copy(update={"source": geometry(3)}))


def sab_result(**changes: object) -> SaveAsBlockResult:
    values: dict[str, object] = {
        "source_revision": "d1",
        "output_path": "C:/out/CleanBlock.dwg",
        "output_revision": "d2",
        "output_digest": DIGEST_B,
        "moved_extent_corner_to_origin": True,
        "base_point_at_origin": True,
        "entities_on_layer_zero": True,
        "entity_color_bylayer": True,
        "entity_linetype_bylayer": True,
        "standard_text_style": True,
        "standard_dimension_style": True,
        "purge_passes": 3,
    }
    values.update(changes)
    return SaveAsBlockResult(**values)


def test_sab_rejects_partial_wblock_and_requires_every_help_normalization() -> None:
    source = DrawingFileSnapshot(
        path="C:/in/BlockSource.dwg",
        revision="d1",
        content_digest=DIGEST_A,
        whole_document=True,
    )
    request = SaveAsBlockRequest(document_id="D", source=source, result=sab_result())
    assert plan_save_as_block(request).file_result.output_digest == DIGEST_B
    with pytest.raises(ValueError, match="whole drawing"):
        plan_save_as_block(
            request.model_copy(update={"source": source.model_copy(update={"whole_document": False})})
        )
    with pytest.raises(ValueError, match="three purges"):
        plan_save_as_block(request.model_copy(update={"result": sab_result(purge_passes=2)}))


def test_ssl_requires_two_points_but_leaves_image_only_geometry_explicit() -> None:
    source = geometry(2)
    request = SectionSymbolRequest(
        document_id="D",
        source=source,
        layer="A-SECT",
        line_type="DASHED",
        result=result(source, layer="A-SECT"),
    )
    assert plan_section_symbol(request).command_alias == "SSL"
    assert any("image" in gap for gap in plan_section_symbol(request).semantic_gaps)


def test_wu_binds_kind_to_selected_layer_and_requires_versioned_linetype() -> None:
    source = geometry(3)
    request = UtilityLineRequest(
        document_id="D",
        source=source,
        kind=UtilityLineKind.RAIN,
        rain_layer="우수관",
        waste_layer="오수관",
        linetype_resource=resource("C:/xicad/linetype-source.lin"),
        result=result(source, layer="우수관"),
    )
    assert plan_utility_line(request).command_alias == "WU"
    with pytest.raises(ValueError, match="selected rain/waste layer"):
        plan_utility_line(request.model_copy(update={"result": result(source, layer="오수관")}))
    short = request.model_copy(update={"source": geometry(1), "result": result(geometry(1))})
    with pytest.raises(ValueError, match="at least two"):
        plan_utility_line(short)


def test_canonical_approval_and_eight_read_only_tools() -> None:
    source = geometry(3)
    request = KitchenCornerRequest(
        document_id="D", source=source, refrigerator_width=900, result=result(source)
    )
    with pytest.raises(ValueError, match="exact approval"):
        KitchenCornerRequest.model_validate(
            request.model_copy(
                update={
                    "dry_run": False,
                    "approval": Approval(approved=True, fingerprint="sha256:wrong"),
                }
            ).model_dump()
        )
    approved = KitchenCornerRequest.model_validate(
        request.model_copy(
            update={
                "dry_run": False,
                "approval": Approval(approved=True, fingerprint=request.fingerprint()),
            }
        ).model_dump()
    )
    assert not plan_kitchen_corner(approved).dry_run

    mcp = FastMCP("batch31b")
    register_headless_core_batch31b_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "xicad_plan_kcl",
        "xicad_plan_plm",
        "xicad_plan_ppb",
        "xicad_plan_rd",
        "xicad_plan_rub",
        "xicad_plan_sab",
        "xicad_plan_ssl",
        "xicad_plan_wu",
    }
    assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
    assert all(tool.annotations and not tool.annotations.destructiveHint for tool in tools)
