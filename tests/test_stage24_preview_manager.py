from src.preview_lifecycle.manager import remove_preview, replace_preview
from src.preview_lifecycle.schema import PreviewSession


def test_remove_preview_dry_run():
    session = PreviewSession(inserted_handle="ABCD")
    result = remove_preview(session, allow_execute=False)
    assert result.executed is False
    assert result.saved is False
    assert result.warnings


def test_remove_preview_without_handle_errors():
    session = PreviewSession()
    result = remove_preview(session, allow_execute=False)
    assert result.errors


def test_replace_preview_dry_run():
    session = PreviewSession(inserted_handle="ABCD")
    result = replace_preview(session, "new.dxf", "out.json", allow_execute=False)
    assert result.executed is False
    assert result.metadata["new_source_dxf"] == "new.dxf"
