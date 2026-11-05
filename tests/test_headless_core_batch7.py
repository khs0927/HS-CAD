from __future__ import annotations

import pytest

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch5 import DrawingSpace, TextEntityKind, TextEntitySnapshot
from xicad_mcp.headless_core_batch7 import (
    FieldTextSnapshot,
    FieldToTextRequest,
    FindMarkRequest,
    JustificationRequest,
    MarkShape,
    PartialTextCopyRequest,
    SearchMode,
    SequentialEdit,
    SequentialEditRequest,
    SourceDisposition,
    SplitMode,
    StackAnchor,
    StackDirection,
    StyleScope,
    SubstringMode,
    TextJustification,
    TextSplitRequest,
    TextStackRequest,
    TextStyleRequest,
    TextSwapRequest,
    TextToMTextRequest,
    TextWidthRequest,
    UnresolvedFieldPolicy,
    plan_field_to_text,
    plan_find_and_mark,
    plan_justification,
    plan_partial_text_copy,
    plan_sequential_edit,
    plan_text_split,
    plan_text_stack,
    plan_text_style,
    plan_text_swap,
    plan_text_to_mtext,
    plan_text_width,
    register_headless_core_batch7_tools,
)


def entity(
    handle: str,
    text: str,
    *,
    x: float = 0,
    y: float = 0,
    kind: TextEntityKind = TextEntityKind.TEXT,
    style: str = "Standard",
    locked: bool = False,
    space: DrawingSpace = DrawingSpace.MODEL,
) -> TextEntitySnapshot:
    return TextEntitySnapshot(
        handle=handle,
        text=text,
        kind=kind,
        layer="TEXT",
        text_style=style,
        text_height=2.5,
        insertion_point=Point3D(x=x, y=y),
        locked_layer=locked,
        space=space,
    )


def approved() -> Approval:
    return Approval(approved=True, fingerprint="sha256:test")


def test_fam_count_honors_case_space_and_whole_string_policies():
    plan = plan_find_and_mark(
        FindMarkRequest(
            document_id="D",
            query="Room A",
            mode=SearchMode.COUNT,
            ignore_spaces=True,
            case_sensitive=False,
            whole_string=True,
        ),
        [entity("1", "ROOMA"), entity("2", "Room A1")],
    )
    assert plan.matched_handles == ("1",)
    assert plan.match_count == 1
    assert plan.markers == ()


def test_fam_mark_contract_captures_recovered_dcl_choices():
    plan = plan_find_and_mark(
        FindMarkRequest(
            document_id="D",
            query="A",
            mode=SearchMode.MARK,
            mark_shape=MarkShape.CIRCLE,
            mark_layer="MARK",
            circle_radius=20,
            mark_insertion_point=True,
        ),
        [entity("1", "A", x=3, y=4)],
    )
    assert plan.markers[0].center == Point3D(x=3, y=4, z=0)
    assert plan.markers[0].radius == 20


def test_fam_block_mark_requires_explicit_block_name():
    with pytest.raises(ValueError, match="block_name"):
        FindMarkRequest(
            document_id="D",
            query="A",
            mode=SearchMode.MARK,
            mark_shape=MarkShape.BLOCK,
            mark_layer="MARK",
        )


def test_ftt_uses_evaluated_value_and_never_evaluates_field_itself():
    plan = plan_field_to_text(
        FieldToTextRequest(
            document_id="D",
            target_handles=("A",),
            unresolved_policy=UnresolvedFieldPolicy.ERROR,
        ),
        [FieldTextSnapshot(handle="A", field_expression="%<field>%", evaluated_text="42")],
    )
    assert plan.changes[0].replacement_text == "42"


def test_ftt_unresolved_policy_is_explicit():
    plan = plan_field_to_text(
        FieldToTextRequest(
            document_id="D",
            target_handles=("A",),
            unresolved_policy=UnresolvedFieldPolicy.KEEP_FIELD,
        ),
        [FieldTextSnapshot(handle="A", field_expression="%<bad>%")],
    )
    assert plan.changes == ()


def test_t2m_requires_single_line_text_and_declares_source_disposition():
    plan = plan_text_to_mtext(
        TextToMTextRequest(
            document_id="D",
            target_handles=("A",),
            source_disposition=SourceDisposition.REPLACE,
            preserve_visual_width=True,
        ),
        [entity("A", "hello")],
    )
    assert plan.conversions[0].erase_source
    assert plan.conversions[0].preserve_visual_width
    with pytest.raises(ValueError, match="single-line"):
        plan_text_to_mtext(
            TextToMTextRequest(
                document_id="D",
                target_handles=("B",),
                source_disposition=SourceDisposition.PRESERVE,
                preserve_visual_width=False,
            ),
            [entity("B", "mtext", kind=TextEntityKind.MTEXT)],
        )


def test_tec_supports_explicit_slice_and_regex_group():
    sliced = plan_partial_text_copy(
        PartialTextCopyRequest(document_id="D", target_handles=("A",), mode=SubstringMode.SLICE, start=5),
        [entity("A", "ROOM-101")],
    )
    regex = plan_partial_text_copy(
        PartialTextCopyRequest(
            document_id="D",
            target_handles=("A",),
            mode=SubstringMode.REGEX_GROUP,
            pattern=r"ROOM-(\d+)",
            group=1,
        ),
        [entity("A", "ROOM-101")],
    )
    assert sliced.extracted[0].value == "101"
    assert regex.extracted[0].value == "101"


def test_tec_read_only_extraction_accepts_locked_source_snapshot():
    plan = plan_partial_text_copy(
        PartialTextCopyRequest(document_id="D", target_handles=("A",), mode=SubstringMode.SLICE, start=0),
        [entity("A", "LOCKED", locked=True)],
    )
    assert plan.extracted[0].value == "LOCKED"


def test_tj_preserve_visual_position_is_not_implicit():
    plan = plan_justification(
        JustificationRequest(
            document_id="D",
            target_handles=("A",),
            justification=TextJustification.CENTER,
            preserve_visual_position=True,
        ),
        [entity("A", "x")],
    )
    assert plan.changes[0].preserve_visual_position


def test_tsa_document_scope_and_tst_selected_scope_are_distinct():
    entities = [entity("A", "a"), entity("B", "b", space=DrawingSpace.PAPER)]
    tsa = plan_text_style(
        TextStyleRequest(document_id="D", target_style="NEW", scope=StyleScope.DOCUMENT),
        entities,
        alias="TSA",
    )
    tst = plan_text_style(
        TextStyleRequest(
            document_id="D",
            target_style="ONE",
            scope=StyleScope.SELECTED,
            target_handles=("A",),
        ),
        entities,
        alias="TST",
    )
    assert {c.handle for c in tsa.changes} == {"A", "B"}
    assert [c.handle for c in tst.changes] == ["A"]


def test_tsa_rejects_locked_document_target():
    with pytest.raises(ValueError, match="locked"):
        plan_text_style(
            TextStyleRequest(document_id="D", target_style="NEW", scope=StyleScope.DOCUMENT),
            [entity("A", "a", locked=True)],
            alias="TSA",
        )


def test_tse_checks_each_expected_value_before_building_changes():
    request = SequentialEditRequest(
        document_id="D",
        edits=(SequentialEdit(handle="A", expected_text="old", replacement_text="new"),),
    )
    assert plan_sequential_edit(request, [entity("A", "old")]).changes[0].replacement_text == "new"
    with pytest.raises(ValueError, match="mismatch"):
        plan_sequential_edit(request, [entity("A", "other")])


def test_tso_vertical_stack_uses_explicit_order_and_gap():
    plan = plan_text_stack(
        TextStackRequest(
            document_id="D",
            target_handles=("A", "B"),
            direction=StackDirection.VERTICAL,
            gap=5,
            anchor=StackAnchor.EXPLICIT,
            anchor_point=Point3D(x=10, y=20),
            order=("B", "A"),
        ),
        [entity("A", "a"), entity("B", "b")],
    )
    assert [m.handle for m in plan.moves] == ["B", "A"]
    assert plan.moves[1].to_point == Point3D(x=10, y=15, z=0)


def test_tso_rejects_duplicate_explicit_order():
    with pytest.raises(ValueError, match="exactly once"):
        TextStackRequest(
            document_id="D",
            target_handles=("A", "B"),
            direction=StackDirection.HORIZONTAL,
            gap=1,
            anchor=StackAnchor.FIRST,
            order=("A", "A", "B"),
        )


def test_tsp_delimiter_split_preserves_or_replaces_source_explicitly():
    plan = plan_text_split(
        TextSplitRequest(
            document_id="D",
            target_handles=("A",),
            mode=SplitMode.DELIMITER,
            delimiter="/",
            source_disposition=SourceDisposition.REPLACE,
            offset=Point3D(x=10, y=0),
        ),
        [entity("A", "A/B/C", x=1, y=2)],
    )
    assert [p.text for p in plan.pieces] == ["A", "B", "C"]
    assert plan.pieces[2].insertion_point.x == 21
    assert plan.erase_source_handles == ("A",)


def test_tsp_fixed_indices_must_be_unambiguous():
    with pytest.raises(ValueError, match="ascending"):
        TextSplitRequest(
            document_id="D",
            target_handles=("A",),
            mode=SplitMode.FIXED_INDEX,
            indices=(3, 2),
            source_disposition=SourceDisposition.PRESERVE,
            offset=Point3D(x=1, y=0),
        )


def test_tsw_swaps_only_text_content():
    plan = plan_text_swap(
        TextSwapRequest(document_id="D", first_handle="A", second_handle="B"),
        [entity("A", "one"), entity("B", "two")],
    )
    assert [c.replacement_text for c in plan.changes] == ["two", "one"]


def test_tw_width_factor_is_bounded_and_applies_to_selected_handles():
    plan = plan_text_width(
        TextWidthRequest(document_id="D", target_handles=("A", "B"), width_factor=0.8),
        [entity("A", "a"), entity("B", "b")],
    )
    assert [c.width_factor for c in plan.changes] == [0.8, 0.8]
    with pytest.raises(ValueError):
        TextWidthRequest(document_id="D", target_handles=("A",), width_factor=0)


def test_live_mode_requires_fingerprinted_approval():
    with pytest.raises(ValueError, match="approval"):
        TextSwapRequest(document_id="D", first_handle="A", second_handle="B", dry_run=False)
    request = TextSwapRequest(
        document_id="D",
        first_handle="A",
        second_handle="B",
        dry_run=False,
        approval=approved(),
    )
    assert request.approval.approved


class FakeMCP:
    def __init__(self) -> None:
        self.tools: list[tuple[str, object]] = []

    def tool(self, *, name: str, annotations: object):
        self.tools.append((name, annotations))

        def decorate(function):
            return function

        return decorate


def test_batch7_registers_twelve_read_only_fastmcp_planners():
    mcp = FakeMCP()
    register_headless_core_batch7_tools(mcp)
    assert [name for name, _ in mcp.tools] == [
        "xicad_plan_fam",
        "xicad_plan_ftt",
        "xicad_plan_t2m",
        "xicad_plan_tec",
        "xicad_plan_tj",
        "xicad_plan_tsa",
        "xicad_plan_tse",
        "xicad_plan_tso",
        "xicad_plan_tsp",
        "xicad_plan_tst",
        "xicad_plan_tsw",
        "xicad_plan_tw",
    ]
    assert all(annotation.readOnlyHint for _, annotation in mcp.tools)
