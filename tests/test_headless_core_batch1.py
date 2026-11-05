from decimal import Decimal

import pytest
from pydantic import ValidationError

from xicad_mcp.headless_core_batch1 import (
    Approval,
    ArcGeometry,
    ArcToCircleRequest,
    DrawingSpace,
    LayerAffixMode,
    LayerAffixRequest,
    LayerNameRef,
    MultiplicationRequest,
    Point3D,
    RotateCopyRequest,
    SourcePolicy,
    TextCountRequest,
    TextGrouping,
    TextRef,
    execute_arc_to_circle,
    execute_layer_affix,
    execute_rotate_copy,
    execute_text_count,
    multiply_numbers,
    plan_arc_to_circle,
    plan_layer_affix,
    plan_rotate_copy,
    plan_text_count,
)


def approved():
    return Approval(approved=True, fingerprint="sha256:test")


class FakeAdapter:
    def __init__(self):
        self.document = "doc-1"
        self.events = []
        self.layers = [
            LayerNameRef(name="0", system=True),
            LayerNameRef(name="A-WALL"),
            LayerNameRef(name="A-DOOR"),
            LayerNameRef(name="XREF|A-WALL", xref_dependent=True),
        ]
        self.texts = [
            TextRef(handle="T1", text="Door"),
            TextRef(handle="T2", text=" door "),
            TextRef(handle="T3", text="Window"),
            TextRef(handle="T4", text="", space=DrawingSpace.PAPER),
        ]
        self.clone_no = 0

    def active_document_id(self):
        return self.document

    def begin_undo_mark(self):
        self.events.append("begin")

    def end_undo_mark(self):
        self.events.append("end")

    def read_arc(self, handle):
        return ArcGeometry(
            handle=handle,
            center=Point3D(x=1, y=2),
            radius=3,
            layer="A-CIRCLE",
        )

    def create_circle(self, geometry):
        self.events.append(("circle", geometry.radius, geometry.layer))
        return "C1"

    def erase_entities(self, handles):
        self.events.append(("erase", tuple(handles)))

    def validate_entity_handles(self, handles):
        self.events.append(("validate", tuple(handles)))

    def clone_entities(self, handles):
        self.clone_no += 1
        result = tuple(f"{handle}-C{self.clone_no}" for handle in handles)
        self.events.append(("clone", tuple(handles), result))
        return result

    def rotate_entities(self, handles, base_point, angle_degrees):
        self.events.append(("rotate", tuple(handles), angle_degrees))

    def list_layers(self):
        return self.layers

    def rename_layers(self, rename_map):
        self.events.append(("rename", rename_map))

    def list_text_entities(self, handles, spaces):
        return self.texts

    def create_text_count_summary(self, records, insertion_point, output_layer):
        self.events.append(("summary", len(records), output_layer))
        return ("S1",)


def test_multiplication_is_exact_and_dialog_free():
    result = multiply_numbers(MultiplicationRequest(operands=(Decimal("1.2"), Decimal("3"), Decimal("2.5"))))
    assert result.result == Decimal("9.00")
    assert result.dialog_required is False
    assert result.cad_required is False


def test_multiplication_rounds_only_when_requested():
    result = multiply_numbers(MultiplicationRequest(operands=(Decimal("2"), Decimal("1.234")), decimal_places=2))
    assert result.exact_product == Decimal("2.468")
    assert result.result == Decimal("2.47")


def test_cp_requires_explicit_source_policy():
    with pytest.raises(ValidationError):
        ArcToCircleRequest(document_id="doc-1", arc_handle="A1")


def test_cp_plan_uses_arc_center_radius_and_layer():
    request = ArcToCircleRequest(document_id="doc-1", arc_handle="A1", source_policy=SourcePolicy.PRESERVE)
    arc = ArcGeometry(handle="A1", center=Point3D(x=5, y=6), radius=7, layer="ARC")
    plan = plan_arc_to_circle(request, arc)
    assert plan.output.center == arc.center
    assert plan.output.radius == 7
    assert plan.output.layer == "ARC"
    assert plan.current_semantic_candidate_alias == "ATC"
    assert not plan.legacy_equivalence_verified_in_cad


def test_cp_replace_executes_inside_one_undo_mark():
    adapter = FakeAdapter()
    result = execute_arc_to_circle(
        ArcToCircleRequest(
            document_id="doc-1",
            arc_handle="A1",
            source_policy=SourcePolicy.REPLACE,
            dry_run=False,
            approval=approved(),
        ),
        adapter,
    )
    assert result.created_handle == "C1"
    assert result.erased_source_handle == "A1"
    assert adapter.events == [
        "begin",
        ("circle", 3.0, "A-CIRCLE"),
        ("erase", ("A1",)),
        "end",
    ]


def test_rc_plan_preserves_originals_and_has_no_dialog():
    plan = plan_rotate_copy(
        RotateCopyRequest(
            document_id="doc-1",
            source_handles=("A", "B"),
            base_point=Point3D(x=0, y=0),
            angle_degrees=30,
            copies=2,
        )
    )
    assert plan.preserve_originals
    assert plan.dialog_required is False
    assert plan.current_semantic_candidate_alias == "CR"


def test_rc_execution_rotates_each_copy_at_incremental_angle():
    adapter = FakeAdapter()
    result = execute_rotate_copy(
        RotateCopyRequest(
            document_id="doc-1",
            source_handles=("A",),
            base_point=Point3D(x=0, y=0),
            angle_degrees=45,
            copies=2,
            dry_run=False,
            approval=approved(),
        ),
        adapter,
    )
    assert result.created_handle_groups == (("A-C1",), ("A-C2",))
    assert ("rotate", ("A-C1",), 45.0) in adapter.events
    assert ("rotate", ("A-C2",), 90.0) in adapter.events
    assert adapter.events[1] == "begin"
    assert adapter.events[-1] == "end"


def test_layer_prefix_plan_skips_system_and_xref_layers():
    adapter = FakeAdapter()
    plan = plan_layer_affix(
        LayerAffixRequest(
            document_id="doc-1",
            mode=LayerAffixMode.PREFIX,
            affix="NEW-",
            target_names=("0", "A-WALL", "XREF|A-WALL"),
        ),
        adapter.layers,
    )
    assert plan.command_alias == "LPP"
    assert [(p.source, p.target) for p in plan.rename_pairs] == [("A-WALL", "NEW-A-WALL")]
    assert plan.skipped_names == ("0", "XREF|A-WALL")


def test_layer_suffix_collision_is_rejected():
    layers = [LayerNameRef(name="A"), LayerNameRef(name="A-X")]
    with pytest.raises(ValueError, match="collision"):
        plan_layer_affix(
            LayerAffixRequest(
                document_id="doc-1",
                mode=LayerAffixMode.SUFFIX,
                affix="-X",
                target_names=("A",),
            ),
            layers,
        )


def test_layer_affix_execution_uses_single_undo_mark():
    adapter = FakeAdapter()
    result = execute_layer_affix(
        LayerAffixRequest(
            document_id="doc-1",
            mode=LayerAffixMode.SUFFIX,
            affix="-OLD",
            target_names=("A-WALL", "A-DOOR"),
            dry_run=False,
            approval=approved(),
        ),
        adapter,
    )
    assert len(result.renamed_pairs) == 2
    assert adapter.events == [
        "begin",
        ("rename", {"A-WALL": "A-WALL-OLD", "A-DOOR": "A-DOOR-OLD"}),
        "end",
    ]


def test_tct_groups_trimmed_casefolded_values_deterministically():
    adapter = FakeAdapter()
    plan = plan_text_count(
        TextCountRequest(document_id="doc-1", grouping=TextGrouping.TRIM_CASEFOLD),
        adapter.texts,
    )
    assert [(r.value, r.count) for r in plan.records] == [
        ("door", 2),
        ("window", 1),
    ]
    assert plan.total_entities == 3
    assert plan.distinct_values == 2


def test_tct_write_requires_insertion_point_and_approval():
    with pytest.raises(ValueError, match="insertion_point"):
        TextCountRequest(document_id="doc-1", write_summary=True)
    with pytest.raises(ValueError, match="approval"):
        TextCountRequest(
            document_id="doc-1",
            write_summary=True,
            insertion_point=Point3D(x=0, y=0),
            dry_run=False,
        )


def test_tct_execution_writes_summary_inside_undo_mark():
    adapter = FakeAdapter()
    result = execute_text_count(
        TextCountRequest(
            document_id="doc-1",
            grouping=TextGrouping.TRIM_CASEFOLD,
            write_summary=True,
            insertion_point=Point3D(x=0, y=0),
            output_layer="T-TEXT",
            dry_run=False,
            approval=approved(),
        ),
        adapter,
    )
    assert result.created_handles == ("S1",)
    assert adapter.events == ["begin", ("summary", 2, "T-TEXT"), "end"]


def test_document_mismatch_rejected_for_mutation_core():
    adapter = FakeAdapter()
    adapter.document = "other"
    with pytest.raises(ValueError, match="mismatch"):
        execute_rotate_copy(
            RotateCopyRequest(
                document_id="doc-1",
                source_handles=("A",),
                base_point=Point3D(x=0, y=0),
                angle_degrees=10,
            ),
            adapter,
        )
