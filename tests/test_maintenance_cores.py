import pytest

from xicad_mcp.maintenance_cores import (
    AllPointDeleteRequest,
    Approval,
    CadPlatform,
    DrawingSpace,
    EntityRef,
    LayerFilterDeleteRequest,
    LayerFilterRef,
    execute_all_point_delete,
    execute_layer_filter_delete,
    legacy_platform_support,
    plan_all_point_delete,
    plan_layer_filter_delete,
)


class FakeAdapter:
    def __init__(self):
        self.document = "doc-1"
        self.entities = [
            EntityRef(handle="A", dxf_type="POINT", space=DrawingSpace.MODEL),
            EntityRef(handle="B", dxf_type="POINT", space=DrawingSpace.PAPER),
        ]
        self.filters = [
            LayerFilterRef(name="Architectural"),
            LayerFilterRef(name="System", system=True),
            LayerFilterRef(name="Keep"),
        ]
        self.events = []

    def active_document_id(self):
        return self.document

    def begin_undo_mark(self):
        self.events.append("begin")

    def end_undo_mark(self):
        self.events.append("end")

    def find_entities(self, dxf_types, spaces):
        return [e for e in self.entities if e.dxf_type in dxf_types and e.space in spaces]

    def erase_entities(self, handles):
        self.events.append(("erase", tuple(handles)))

    def list_layer_filters(self):
        return self.filters

    def delete_layer_filters(self, names):
        self.events.append(("delete_filters", tuple(names)))


def approval():
    return Approval(approved=True, fingerprint="sha256:test")


def test_apd_plan_is_destructive_but_not_live():
    p = plan_all_point_delete(AllPointDeleteRequest(document_id="doc-1"))
    assert p.dxf_types == ("POINT",)
    assert p.destructive
    assert not p.production_usable


def test_apd_dry_run_has_no_mutation():
    a = FakeAdapter()
    r = execute_all_point_delete(AllPointDeleteRequest(document_id="doc-1"), a)
    assert r.matched_handles == ("A", "B")
    assert not r.deleted_handles
    assert a.events == []


def test_apd_requires_approval():
    with pytest.raises(ValueError):
        AllPointDeleteRequest(document_id="doc-1", dry_run=False)


def test_apd_executes_inside_undo_mark():
    a = FakeAdapter()
    r = execute_all_point_delete(AllPointDeleteRequest(document_id="doc-1", dry_run=False, approval=approval()), a)
    assert r.deleted_handles == ("A", "B")
    assert a.events == ["begin", ("erase", ("A", "B")), "end"]
    assert r.undo_mark_closed


def test_document_mismatch_rejected():
    a = FakeAdapter()
    with pytest.raises(ValueError):
        execute_all_point_delete(AllPointDeleteRequest(document_id="other"), a)


def test_layer_filter_plan_preserves_system_and_named_filters():
    req = LayerFilterDeleteRequest(document_id="doc-1", preserve_names=("Keep",))
    p = plan_layer_filter_delete(req, FakeAdapter().filters)
    assert p.selected_names == ("Architectural",)
    assert p.preserved_names == ("Keep", "System")


def test_layer_filter_shared_aliases():
    p = plan_layer_filter_delete(LayerFilterDeleteRequest(document_id="doc-1"), FakeAdapter().filters)
    assert p.command_aliases == ("LFD", "LPD")
    assert p.shared_core_key == "layer_filters_delete"


def test_layer_filter_execution_uses_undo():
    a = FakeAdapter()
    r = execute_layer_filter_delete(
        LayerFilterDeleteRequest(document_id="doc-1", preserve_names=("Keep",), dry_run=False, approval=approval()), a
    )
    assert r.deleted_names == ("Architectural",)
    assert a.events == ["begin", ("delete_filters", ("Architectural",)), "end"]


def test_specific_layer_filter_mode_requires_names():
    with pytest.raises(ValueError):
        LayerFilterDeleteRequest(document_id="doc-1", delete_all_user_filters=False)


def test_sld_is_explicitly_unsupported_on_zwcad():
    p = legacy_platform_support("SLD", CadPlatform.ZWCAD)
    assert not p.supported
    assert p.implementation_state == "platform_excluded"
    assert not p.production_usable
