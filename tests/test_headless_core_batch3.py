import pytest
from pydantic import ValidationError

from xicad_mcp.headless_core_batch1 import Approval, Point3D
from xicad_mcp.headless_core_batch3 import (
    AttributeBlockRotateRequest,
    AttributeBlockSnapshot,
    AttributePreservation,
    BlockRecordSnapshot,
    DgnLinetypePurgeRequest,
    DoorHinge,
    DoorSwing,
    GhostClassification,
    GhostCleanupRequest,
    GhostObjectSnapshot,
    LinetypeOrigin,
    LinetypeSnapshot,
    NullBlockCleanupRequest,
    RotationMode,
    ToiletBoothLegacyVariant,
    ToiletBoothRequest,
    execute_attribute_block_rotate,
    execute_dgn_linetype_purge,
    execute_ghost_cleanup,
    execute_null_block_cleanup,
    execute_toilet_booth,
    plan_attribute_block_rotate,
    plan_dgn_linetype_purge,
    plan_ghost_cleanup,
    plan_null_block_cleanup,
    plan_toilet_booth,
)


def approved():
    return Approval(approved=True, fingerprint="sha256:test")


class FakeAdapter:
    def __init__(self):
        self.document = "doc-1"
        self.events = []
        self.blocks = [
            AttributeBlockSnapshot(
                handle="B1",
                block_name="TAG_BLOCK",
                current_rotation_degrees=10,
                attribute_handles=("A1", "A2"),
                non_attribute_entity_count=4,
            )
        ]
        self.block_records = [
            BlockRecordSnapshot(handle="R1", name="EMPTY", reference_count=0, entity_count=0),
            BlockRecordSnapshot(handle="R2", name="USED", reference_count=1, entity_count=0),
            BlockRecordSnapshot(handle="R3", name="*Model_Space", reference_count=0, entity_count=0, is_layout=True),
        ]
        self.ghosts = [
            GhostObjectSnapshot(
                handle="G1",
                object_type="AcDbLine",
                classification=GhostClassification.ORPHANED_OWNER,
                hard_reference_count=0,
            ),
            GhostObjectSnapshot(
                handle="G2",
                object_type="AcDbDictionary",
                classification=GhostClassification.ERASED_RESIDENT,
                hard_reference_count=0,
                is_dictionary_entry=True,
            ),
            GhostObjectSnapshot(
                handle="G3",
                object_type="AcDbCircle",
                classification=GhostClassification.ORPHANED_OWNER,
                hard_reference_count=1,
            ),
        ]
        self.linetypes = [
            LinetypeSnapshot(
                handle="L1", name="DGN-1", origin=LinetypeOrigin.DGN, in_use=False, dependent_resource_count=0
            ),
            LinetypeSnapshot(
                handle="L2", name="DGN-USED", origin=LinetypeOrigin.DGN, in_use=True, dependent_resource_count=0
            ),
            LinetypeSnapshot(
                handle="L3",
                name="Continuous",
                origin=LinetypeOrigin.CAD,
                in_use=False,
                dependent_resource_count=0,
                is_reserved=True,
            ),
        ]

    def active_document_id(self):
        return self.document

    def begin_undo_mark(self):
        self.events.append("begin")

    def end_undo_mark(self):
        self.events.append("end")

    def read_attribute_blocks(self, handles):
        return self.blocks

    def rotate_block_non_attribute_geometry(self, handle, delta, preservation):
        self.events.append(("bar", handle, delta, preservation.value))

    def list_block_records(self):
        return self.block_records

    def purge_block_records(self, handles):
        self.events.append(("abd", tuple(handles)))
        return tuple(handles)

    def inspect_ghost_objects(self):
        return self.ghosts

    def remove_database_objects(self, handles):
        self.events.append(("agd", tuple(handles)))
        return tuple(handles)

    def list_linetypes(self):
        return self.linetypes

    def purge_linetypes(self, handles):
        self.events.append(("lpu", tuple(handles)))
        return tuple(handles)

    def create_lines(self, specs):
        self.events.append(("lines", len(specs)))
        return tuple(f"LN{i}" for i in range(len(specs)))

    def create_arcs(self, specs):
        self.events.append(("arcs", len(specs)))
        return tuple(f"AR{i}" for i in range(len(specs)))


def test_bar_absolute_rotation_computes_delta_and_preservation_policy():
    request = AttributeBlockRotateRequest(
        document_id="doc-1",
        block_handles=("B1",),
        rotation_mode=RotationMode.ABSOLUTE,
        angle_degrees=40,
        attribute_preservation=AttributePreservation.WORLD_POSITION_AND_ROTATION,
    )
    plan = plan_attribute_block_rotate(request, FakeAdapter().blocks)
    assert plan.operations[0].delta_degrees == 30
    assert plan.operations[0].target_rotation_degrees == 40
    assert plan.dialog_required is False


def test_bar_execution_uses_explicit_high_level_adapter_capability():
    adapter = FakeAdapter()
    result = execute_attribute_block_rotate(
        AttributeBlockRotateRequest(
            document_id="doc-1",
            block_handles=("B1",),
            rotation_mode=RotationMode.DELTA,
            angle_degrees=15,
            attribute_preservation=AttributePreservation.WORLD_ROTATION_ONLY,
            dry_run=False,
            approval=approved(),
        ),
        adapter,
    )
    assert result.changed_block_handles == ("B1",)
    assert adapter.events == ["begin", ("bar", "B1", 15.0, "world_rotation_only"), "end"]


def test_abd_only_selects_empty_unreferenced_unprotected_records():
    plan = plan_null_block_cleanup(NullBlockCleanupRequest(document_id="doc-1"), FakeAdapter().block_records)
    assert plan.purge_handles == ("R1",)
    assert {s.reason for s in plan.skipped} == {"still_referenced", "preserved_by_request"}


def test_abd_target_and_preserve_overlap_is_rejected():
    with pytest.raises(ValueError, match="overlap"):
        NullBlockCleanupRequest(document_id="doc-1", target_names=("A",), preserve_names=("a",))


def test_abd_execution_purges_approved_set_inside_undo():
    adapter = FakeAdapter()
    result = execute_null_block_cleanup(
        NullBlockCleanupRequest(document_id="doc-1", dry_run=False, approval=approved()),
        adapter,
    )
    assert result.removed_handles == ("R1",)
    assert adapter.events == ["begin", ("abd", ("R1",)), "end"]


def test_agd_requires_explicit_classification_acceptance():
    with pytest.raises(ValidationError):
        GhostCleanupRequest(document_id="doc-1", accepted_classifications=())


def test_agd_skips_protected_and_referenced_objects():
    request = GhostCleanupRequest(
        document_id="doc-1",
        accepted_classifications=(GhostClassification.ORPHANED_OWNER, GhostClassification.ERASED_RESIDENT),
    )
    plan = plan_ghost_cleanup(request, FakeAdapter().ghosts)
    assert plan.remove_handles == ("G1",)
    assert {s.reason for s in plan.skipped} == {"protected_database_object", "hard_referenced"}


def test_agd_execution_removes_only_planned_handles():
    adapter = FakeAdapter()
    result = execute_ghost_cleanup(
        GhostCleanupRequest(
            document_id="doc-1",
            accepted_classifications=(GhostClassification.ORPHANED_OWNER,),
            dry_run=False,
            approval=approved(),
        ),
        adapter,
    )
    assert result.removed_handles == ("G1",)
    assert adapter.events == ["begin", ("agd", ("G1",)), "end"]


def test_lpu_selects_unused_dgn_linetypes_only():
    plan = plan_dgn_linetype_purge(DgnLinetypePurgeRequest(document_id="doc-1"), FakeAdapter().linetypes)
    assert plan.purge_handles == ("L1",)
    assert plan.skipped[0].reason == "linetype_in_use"


def test_lpu_requires_targets_when_all_dgn_disabled():
    with pytest.raises(ValueError, match="target_names"):
        DgnLinetypePurgeRequest(document_id="doc-1", include_all_dgn=False)


def test_lpu_execution_supports_bounded_repeated_purge():
    adapter = FakeAdapter()
    result = execute_dgn_linetype_purge(
        DgnLinetypePurgeRequest(document_id="doc-1", dry_run=False, approval=approved()),
        adapter,
    )
    assert result.removed_handles == ("L1",)
    assert adapter.events == ["begin", ("lpu", ("L1",)), "end"]


def booth_request(variant=ToiletBoothLegacyVariant.MTB1, **overrides):
    values = dict(
        document_id="doc-1",
        legacy_variant=variant,
        origin=Point3D(x=0, y=0),
        direction_degrees=0,
        stall_count=2,
        stall_width=1.0,
        stall_depth=1.5,
        door_width=0.6,
        door_clearance_from_side=0.1,
        door_hinges=(DoorHinge.LEFT, DoorHinge.RIGHT),
        door_swing=DoorSwing.INWARD,
        layer="A-TOILET",
    )
    values.update(overrides)
    return ToiletBoothRequest(**values)


def test_mtb_shared_core_generates_explicit_two_stall_geometry():
    plan = plan_toilet_booth(booth_request())
    assert plan.command_alias == "MTB1"
    assert plan.shared_core_key == "toilet_booth_geometry"
    assert len(plan.wall_lines) == 8  # back, 2 ends, partition, 4 front segments
    assert len(plan.door_leaf_lines) == 2
    assert len(plan.door_swing_arcs) == 2
    assert plan.legacy_variant_behavior_inferred is False


def test_mtb2_uses_same_core_without_inferred_behavior():
    plan = plan_toilet_booth(booth_request(ToiletBoothLegacyVariant.MTB2))
    assert plan.command_alias == "MTB2"
    assert plan.legacy_symbol == "xiMakeToiletBooth2"
    assert plan.legacy_variant_behavior_inferred is False


def test_mtb_rejects_door_that_does_not_fit():
    with pytest.raises(ValueError, match="does not fit"):
        booth_request(door_width=0.9, door_clearance_from_side=0.2)


def test_mtb_execution_creates_lines_and_arcs_in_one_undo_mark():
    adapter = FakeAdapter()
    result = execute_toilet_booth(
        booth_request(dry_run=False, approval=approved()),
        adapter,
    )
    assert len(result.created_handles) == 12
    assert adapter.events == ["begin", ("lines", 10), ("arcs", 2), "end"]


def test_document_mismatch_is_rejected():
    adapter = FakeAdapter()
    adapter.document = "other"
    with pytest.raises(ValueError, match="mismatch"):
        execute_null_block_cleanup(NullBlockCleanupRequest(document_id="doc-1"), adapter)
