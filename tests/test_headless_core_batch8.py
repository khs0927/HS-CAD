from decimal import Decimal

import pytest

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch5 import TextEntityKind, TextEntitySnapshot
from xicad_mcp.headless_core_batch8 import (
    AttributeBlockEditRequest,
    AttributeBlockSnapshot,
    AttributeConversionMode,
    AttributeEditSpec,
    AttributeOperation,
    AttributeSnapshot,
    AttributeToTextRequest,
    ComprehensiveTextEditRequest,
    ComprehensiveTextPatch,
    ContainerAlignment,
    ContainerSnapshot,
    ContextReplacementPolicy,
    ContextSelectionPrecedence,
    ContextTextEditRequest,
    DynamicTitleRequest,
    EqualSpacingTextRequest,
    FrameFitMode,
    MTextFrameFitRequest,
    MTextFrameSnapshot,
    ShadowRepresentation,
    SourceDisposition,
    StyleMergeRequest,
    TextCenterRequest,
    TextContainerPair,
    TextCopyDestination,
    TextCopyPlacement,
    TextCopyRequest,
    TextShadowRequest,
    plan_attribute_block_edit,
    plan_attribute_to_text,
    plan_comprehensive_text_edit,
    plan_context_text_edit,
    plan_dynamic_title,
    plan_equal_spacing_text,
    plan_mtext_frame_fit,
    plan_style_merge,
    plan_text_center,
    plan_text_copy,
    plan_text_shadow,
    register_headless_core_batch8_tools,
)


def entity(handle: str, text: str, *, x: float = 0, y: float = 0, style: str = "Standard", locked=False):
    return TextEntitySnapshot(
        handle=handle,
        text=text,
        kind=TextEntityKind.TEXT,
        layer="TEXT",
        text_style=style,
        text_height=2.5,
        insertion_point=Point3D(x=x, y=y),
        locked_layer=locked,
    )


def attribute(handle: str, owner: str, tag: str, value: str):
    return AttributeSnapshot(
        handle=handle,
        owner_block_handle=owner,
        tag=tag,
        value=value,
        insertion_point=Point3D(x=0, y=0),
        layer="TEXT",
        text_style="Standard",
        text_height=2.5,
    )


def approved():
    return Approval(approved=True, fingerprint="sha256:test")


def test_a2m_single_attribute_to_text_can_include_tag():
    plan = plan_attribute_to_text(
        AttributeToTextRequest(
            document_id="D",
            target_handles=("A",),
            mode=AttributeConversionMode.ATTRIBUTE_TO_TEXT,
            include_tag=True,
            source_disposition=SourceDisposition.PRESERVE,
        ),
        [attribute("A", "B", "ROOM", "101")],
    )
    assert plan.conversions[0].text == "ROOM: 101"
    assert plan.conversions[0].output_kind is TextEntityKind.TEXT
    assert not plan.conversions[0].erase_source


def test_a2m_block_mode_groups_attributes_by_owner():
    plan = plan_attribute_to_text(
        AttributeToTextRequest(
            document_id="D",
            target_handles=("A", "B"),
            mode=AttributeConversionMode.BLOCK_ATTRIBUTES_TO_MTEXT,
            include_tag=False,
            block_separator=" / ",
            source_disposition=SourceDisposition.REPLACE,
        ),
        [attribute("A", "BLK", "X", "one"), attribute("B", "BLK", "Y", "two")],
    )
    assert len(plan.conversions) == 1
    assert plan.conversions[0].text == "one / two"
    assert plan.conversions[0].erase_source


def test_abe_applies_explicit_numeric_operation_and_missing_tag_policy():
    block = AttributeBlockSnapshot(handle="B", name="ROOM", attributes={"COUNT": "10"})
    plan = plan_attribute_block_edit(
        AttributeBlockEditRequest(
            document_id="D",
            target_block_handles=("B",),
            edits=(AttributeEditSpec(tag="COUNT", operation=AttributeOperation.ADD, value=Decimal("2.5")),),
            missing_tag_policy="error",
        ),
        [block],
    )
    assert plan.changes[0].replacement_value == "12.5"


def test_abe_rejects_nested_block_unless_explicitly_included():
    request = AttributeBlockEditRequest(
        document_id="D",
        target_block_handles=("B",),
        edits=(AttributeEditSpec(tag="X", operation=AttributeOperation.SET, value="Y"),),
        missing_tag_policy="error",
    )
    with pytest.raises(ValueError, match="scope"):
        plan_attribute_block_edit(
            request,
            [AttributeBlockSnapshot(handle="B", name="N", attributes={"X": "x"}, nested=True)],
        )


def test_ctx_first_and_whole_entity_policies_are_distinct():
    base = dict(
        document_id="D",
        target_handles=("A",),
        old_text="ab",
        new_text="X",
        selection_precedence=ContextSelectionPrecedence.OBJECT_FIRST,
        whole_string_match=False,
        zoom_text_height_factor=3,
    )
    first = plan_context_text_edit(
        ContextTextEditRequest(**base, replacement_policy=ContextReplacementPolicy.FIRST_PER_ENTITY),
        [entity("A", "ab-ab")],
    )
    whole = plan_context_text_edit(
        ContextTextEditRequest(**base, replacement_policy=ContextReplacementPolicy.REPLACE_WHOLE_ENTITY),
        [entity("A", "ab-ab")],
    )
    assert first.changes[0].replacement_text == "X-ab"
    assert whole.changes[0].replacement_text == "X"


def test_tc_requires_destination_specific_fields_and_builds_both_outputs():
    with pytest.raises(ValueError, match="table_cell"):
        TextCopyPlacement(source_handle="A", destination=TextCopyDestination.TABLE_CELL)
    plan = plan_text_copy(
        TextCopyRequest(
            document_id="D",
            placements=(
                TextCopyPlacement(source_handle="A", destination=TextCopyDestination.NEW_TEXT,
                                  insertion_point=Point3D(x=5, y=5)),
                TextCopyPlacement(source_handle="B", destination=TextCopyDestination.TABLE_CELL,
                                  table_handle="T", row=1, column=2, expected_cell_text="old"),
            ),
        ),
        [entity("A", "copy"), entity("B", "cell")],
    )
    assert plan.creates[0].text == "copy"
    assert plan.table_changes[0].replacement_text == "cell"


def test_tc_can_copy_one_source_to_multiple_destinations():
    plan = plan_text_copy(
        TextCopyRequest(
            document_id="D",
            placements=(
                TextCopyPlacement(source_handle="A", destination=TextCopyDestination.NEW_TEXT,
                                  insertion_point=Point3D(x=1, y=0)),
                TextCopyPlacement(source_handle="A", destination=TextCopyDestination.NEW_TEXT,
                                  insertion_point=Point3D(x=2, y=0)),
            ),
        ),
        [entity("A", "copy")],
    )
    assert len(plan.creates) == 2


def test_te_requires_nonempty_patch_and_expected_text_match():
    with pytest.raises(ValueError, match="at least one"):
        ComprehensiveTextPatch(handle="A")
    request = ComprehensiveTextEditRequest(
        document_id="D",
        patches=(ComprehensiveTextPatch(handle="A", expected_text="old", target_style="NEW"),),
    )
    assert plan_comprehensive_text_edit(request, [entity("A", "old")]).changes[0].target_style == "NEW"
    with pytest.raises(ValueError, match="mismatch"):
        plan_comprehensive_text_edit(request, [entity("A", "other")])


def test_tff_uses_supplied_measured_width_and_explicit_padding_policy():
    frame = MTextFrameSnapshot(handle="A", current_width=100, measured_content_width=40, text_height=5)
    plan = plan_mtext_frame_fit(
        MTextFrameFitRequest(
            document_id="D",
            target_handles=("A",),
            mode=FrameFitMode.HEIGHT_MULTIPLE_PADDING,
            horizontal_padding_height_factor=1,
        ),
        [frame],
    )
    assert plan.changes[0].replacement_width == 50


def test_to_center_and_toa_left_margin_use_normalized_container_geometry():
    request = TextCenterRequest(
        document_id="D",
        pairs=(TextContainerPair(text_handle="A", container_handle="R"),),
        alignment=ContainerAlignment.CENTER,
    )
    box = ContainerSnapshot(handle="R", center=Point3D(x=10, y=20), width=20, height=10)
    centered = plan_text_center(request, [entity("A", "x")], [box], alias="TO")
    assert centered.moves[0].to_point == Point3D(x=10, y=20, z=0)
    left = plan_text_center(
        request.model_copy(update={"alignment": ContainerAlignment.LEFT, "horizontal_margin_height_factor": 2}),
        [entity("A", "x")],
        [box],
        alias="TOA",
    )
    assert left.moves[0].to_point.x == 5


def test_toa_line_gap_is_applied_when_multiple_texts_share_a_container():
    request = TextCenterRequest(
        document_id="D",
        pairs=(
            TextContainerPair(text_handle="A", container_handle="R"),
            TextContainerPair(text_handle="B", container_handle="R"),
        ),
        alignment=ContainerAlignment.CENTER,
        line_gap_height_factor=2,
    )
    box = ContainerSnapshot(handle="R", center=Point3D(x=0, y=0), width=20, height=10)
    plan = plan_text_center(request, [entity("A", "a"), entity("B", "b")], [box], alias="TOA")
    assert [move.to_point.y for move in plan.moves] == [2.5, -2.5]


def test_tsh_representation_and_offset_are_explicit():
    plan = plan_text_shadow(
        TextShadowRequest(
            document_id="D",
            target_handles=("A",),
            representation=ShadowRepresentation.SOLID_OUTLINE,
            offset=Point3D(x=2, y=-3),
            layer="SHADOW",
            color_index=8,
        ),
        [entity("A", "x", x=10, y=10)],
    )
    assert plan.shadows[0].insertion_point == Point3D(x=12, y=7, z=0)


def test_tsm_reassigns_entities_and_optionally_removes_source_styles():
    plan = plan_style_merge(
        StyleMergeRequest(
            document_id="D",
            source_styles=("OLD1", "OLD2"),
            target_style="NEW",
            remove_source_styles=True,
        ),
        [entity("A", "a", style="OLD1"), entity("B", "b", style="NEW")],
    )
    assert plan.entity_style_changes == {"A": "NEW"}
    assert plan.remove_style_names == ("OLD1", "OLD2")


def test_tsm_rejects_target_as_source():
    with pytest.raises(ValueError, match="cannot be a source"):
        StyleMergeRequest(document_id="D", source_styles=("A",), target_style="a", remove_source_styles=False)


def test_dat_requires_explicit_field_expression_and_preserves_preview():
    with pytest.raises(ValueError, match="field expression"):
        DynamicTitleRequest(
            document_id="D", field_expression="filename", preview_text="A.dwg",
            insertion_point=Point3D(x=0, y=0), layer="TITLE", text_style="Standard", text_height=2.5,
        )
    plan = plan_dynamic_title(DynamicTitleRequest(
        document_id="D", field_expression="%<\\AcVar Filename>%", preview_text="A.dwg",
        insertion_point=Point3D(x=0, y=0), layer="TITLE", text_style="Standard", text_height=2.5,
    ))
    assert plan.preview.text == "A.dwg"


def test_ltx_builds_equal_vector_spaced_writes():
    plan = plan_equal_spacing_text(EqualSpacingTextRequest(
        document_id="D", texts=("A", "B", "C"), start_point=Point3D(x=1, y=2),
        step_vector=Point3D(x=5, y=-1), layer="TEXT", text_style="Standard", text_height=2.5,
    ))
    assert plan.creates[2].insertion_point == Point3D(x=11, y=0, z=0)


def test_mutating_live_mode_requires_fingerprinted_approval():
    with pytest.raises(ValueError, match="approval"):
        TextShadowRequest(document_id="D", target_handles=("A",), representation=ShadowRepresentation.TEXT_COPY,
                          offset=Point3D(x=1, y=1), layer="S", color_index=1, dry_run=False)
    request = StyleMergeRequest(document_id="D", source_styles=("A",), target_style="B",
                                remove_source_styles=False, dry_run=False, approval=approved())
    assert request.approval.approved


class FakeMCP:
    def __init__(self):
        self.tools = []

    def tool(self, *, name, annotations):
        self.tools.append((name, annotations))

        def decorate(function):
            return function

        return decorate


def test_batch8_registers_twelve_read_only_fastmcp_planners():
    mcp = FakeMCP()
    register_headless_core_batch8_tools(mcp)
    assert [name for name, _ in mcp.tools] == [
        "xicad_plan_a2m", "xicad_plan_abe", "xicad_plan_ctx", "xicad_plan_tc",
        "xicad_plan_te", "xicad_plan_tff", "xicad_plan_to", "xicad_plan_toa",
        "xicad_plan_tsh", "xicad_plan_tsm", "xicad_plan_dat", "xicad_plan_ltx",
    ]
    assert all(annotation.readOnlyHint for _, annotation in mcp.tools)
