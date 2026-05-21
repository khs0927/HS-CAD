import pytest

from image_to_cad.auto.undo_guard import block_purge_delete_explode, create_undo_mark, undo_back_to_mark


class FakeDoc:
    def __init__(self):
        self.commands = []

    def SendCommand(self, command):
        self.commands.append(command)


def test_undo_mark_and_back_commands():
    doc = FakeDoc()
    assert create_undo_mark(doc) is True
    assert undo_back_to_mark(doc) is True
    assert doc.commands == ["UNDO MARK\n", "UNDO BACK\n"]


def test_forbidden_commands_raise():
    with pytest.raises(PermissionError):
        block_purge_delete_explode("PURGE")
    with pytest.raises(PermissionError):
        block_purge_delete_explode("SAVEAS")
