from __future__ import annotations

import pytest

from xicad_mcp import live_gap_15_16_next as live
from xicad_mcp.headless_core_batch15 import GroupEditRequest, GroupOperation


class Collection:
    def __init__(self, items=()):
        self.items = list(items)

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        return self.items[index]

    def __iter__(self):
        return iter(self.items)


class Entity:
    def __init__(self, handle):
        self.Handle = handle


class Group(Collection):
    def __init__(self, name, items=()):
        super().__init__(items)
        self.Name = name

    def AppendItems(self, items):
        self.items.extend(items)

    def RemoveItems(self, items):
        remove_ids = {id(item) for item in items}
        self.items = [item for item in self.items if id(item) not in remove_ids]


class Groups(Collection):
    pass


class Doc:
    def __init__(self):
        self.Name = "Drawing1.dwg"
        self.e1 = Entity("A1")
        self.e2 = Entity("B2")
        self.e3 = Entity("C3")
        self.group = Group("*A1", (self.e1, self.e2))
        self.Groups = Groups((self.group,))
        self.Blocks = Collection((Collection((self.e1, self.e2, self.e3)),))
        self.Blocks.items[0].IsLayout = True
        self.started = 0
        self.ended = 0

    def StartUndoMark(self):
        self.started += 1

    def EndUndoMark(self):
        self.ended += 1


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> Doc:
    value = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: value)
    monkeypatch.setattr(live, "_dispatch_array", tuple)
    return value


def _execute(preview, request):
    return live.execute_live_gee(
        live.LiveGeeExecuteRequest(
            request=request,
            expected_group=preview["expected_group"],
            approval_fingerprint=preview["approval_fingerprint"],
        )
    )


def test_gee_adds_exact_members_under_one_undo_mark(doc: Doc) -> None:
    request = GroupEditRequest(
        document_id=doc.Name,
        group_name="*A1",
        operation=GroupOperation.ADD_MEMBERS,
        member_handles=("C3",),
    )
    preview = live.preview_live_gee(request)
    result = _execute(preview, request)

    assert {item.Handle for item in doc.group.items} == {"A1", "B2", "C3"}
    assert result.resulting_member_handles == ("A1", "B2", "C3")
    assert result.postcondition_verified
    assert doc.started == doc.ended == 1


def test_gee_removes_members_case_insensitively(doc: Doc) -> None:
    request = GroupEditRequest(
        document_id=doc.Name,
        group_name="*a1",
        operation=GroupOperation.REMOVE_MEMBERS,
        member_handles=("b2",),
    )
    result = _execute(live.preview_live_gee(request), request)

    assert result.resulting_member_handles == ("A1",)
    assert [item.Handle for item in doc.group.items] == ["A1"]


def test_gee_renames_group_and_rejects_name_collision(doc: Doc) -> None:
    request = GroupEditRequest(
        document_id=doc.Name,
        group_name="*A1",
        operation=GroupOperation.RENAME,
        new_name="DOOR-GROUP",
    )
    result = _execute(live.preview_live_gee(request), request)
    assert result.resulting_group_name == "DOOR-GROUP"

    doc.group.Name = "*A1"
    doc.Groups.items.append(Group("TAKEN"))
    colliding = request.model_copy(update={"new_name": "taken"})
    with pytest.raises(ValueError, match="already exists"):
        live.preview_live_gee(colliding)


def test_gee_rejects_stale_group_missing_handle_and_bad_fingerprint(doc: Doc) -> None:
    request = GroupEditRequest(
        document_id=doc.Name,
        group_name="*A1",
        operation=GroupOperation.ADD_MEMBERS,
        member_handles=("C3",),
    )
    preview = live.preview_live_gee(request)
    doc.group.items.pop()
    with pytest.raises(ValueError, match="no longer matches"):
        _execute(preview, request)

    missing = request.model_copy(update={"member_handles": ("404",)})
    with pytest.raises(ValueError, match="unavailable"):
        live.preview_live_gee(missing)

    execute = live.LiveGeeExecuteRequest(
        request=request,
        expected_group=preview["expected_group"],
        approval_fingerprint="sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_gee(execute)


def test_registration_exposes_only_bounded_gee_live_tools() -> None:
    registered = []

    class MCP:
        def tool(self, *, name, annotations):
            registered.append((name, annotations))
            return lambda function: function

    live.register_live_gap_15_16_next_tools(MCP())
    assert [name for name, _ in registered] == ["xicad_preview_live_gee", "xicad_execute_live_gee"]
    assert set(live.LIVE_BLOCKED_REASONS) == {
        "STL",
        "COM",
        "EXP",
        "OL",
        "ON",
        "QQ",
        "BPT",
        "CW",
        "D1",
        "D2",
        "D3",
    }
    assert registered[0][1].readOnlyHint is True
    assert registered[1][1].destructiveHint is True
