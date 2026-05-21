from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator


ALLOWED_UNDO_COMMANDS = {"UNDO MARK", "UNDO BACK"}


def create_undo_mark(doc=None) -> bool:
    doc = doc or _active_doc()
    return _send_allowed_undo(doc, "UNDO MARK")


def undo_back_to_mark(doc=None) -> bool:
    doc = doc or _active_doc()
    return _send_allowed_undo(doc, "UNDO BACK")


def _send_allowed_undo(doc, command: str) -> bool:
    if command not in ALLOWED_UNDO_COMMANDS:
        raise PermissionError(f"Raw command is not allowed: {command}")
    try:
        doc.SendCommand(command + "\n")
        return True
    except Exception:
        return False


def _active_doc():
    from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter

    adapter = ZWCADCOMAdapter(visible=True, start_if_needed=False)
    adapter.connect()
    return adapter.get_active_document()


@contextmanager
def no_save_guard() -> Iterator[None]:
    """Document intent: preview operations must not call Save/SaveAs."""
    yield


def block_purge_delete_explode(command: str) -> None:
    forbidden = {"PURGE", "DELETE", "ERASE", "EXPLODE", "SAVE", "SAVEAS"}
    tokens = {part.strip().upper() for part in str(command).replace("_", " ").split()}
    if forbidden & tokens:
        raise PermissionError(f"Forbidden preview command: {command}")
