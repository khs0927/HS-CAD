from __future__ import annotations

import pytest

from xicad_mcp.file_transaction_contracts import (
    DrawingStateSnapshot,
    FileOperationKind,
    FileSnapshot,
    FileTransactionRequest,
    OverwritePolicy,
    canonical_windows_path,
    plan_file_transaction,
)

DIGEST = "sha256:" + "0" * 64


def _drawing(*, active_command_count: int = 0) -> DrawingStateSnapshot:
    return DrawingStateSnapshot(
        document_name="Drawing1.dwg",
        full_path=r"C:\projects\Drawing1.dwg",
        modified=False,
        active_command_count=active_command_count,
        open_document_names=("Drawing1.dwg",),
    )


def _missing(path: str) -> FileSnapshot:
    return FileSnapshot(path=path, exists=False)


def _existing(path: str, size_bytes: int = 100) -> FileSnapshot:
    return FileSnapshot(path=path, exists=True, size_bytes=size_bytes, digest=DIGEST)


def test_canonical_windows_path_normalizes_case_and_separators() -> None:
    assert canonical_windows_path("C:/Projects/Test.dwg") == r"c:\projects\test.dwg"


@pytest.mark.parametrize(
    "path",
    [r"..\test.dwg", r"C:\projects\..\test.dwg", r"\\server\share\test.dwg"],
)
def test_canonical_windows_path_rejects_unbounded_paths(path: str) -> None:
    with pytest.raises(ValueError):
        canonical_windows_path(path)


def test_save_as_plan_uses_temp_file_and_atomic_commit_steps() -> None:
    request = FileTransactionRequest(
        operation=FileOperationKind.SAVE_AS,
        allowed_roots=(r"C:\projects",),
        destination_path=r"C:\projects\out\saved.dwg",
        overwrite_policy=OverwritePolicy.FORBID,
        expected_destination=_missing(r"C:\projects\out\saved.dwg"),
        expected_drawing=_drawing(),
    )

    plan = plan_file_transaction(request)

    assert plan.canonical_destination_path == r"c:\projects\out\saved.dwg"
    assert plan.temporary_path is not None
    assert plan.temporary_path.endswith(".tmp")
    assert any("atomically replace" in step for step in plan.commit_steps)
    assert not plan.live_executable


def test_require_match_needs_existing_destination_digest() -> None:
    with pytest.raises(ValueError, match="existing destination snapshot with digest"):
        FileTransactionRequest(
            operation=FileOperationKind.PLOT,
            allowed_roots=(r"C:\plots",),
            destination_path=r"C:\plots\sheet.pdf",
            overwrite_policy=OverwritePolicy.REQUIRE_MATCH,
            expected_destination=_missing(r"C:\plots\sheet.pdf"),
            expected_drawing=_drawing(),
        )


def test_request_rejects_destination_outside_allowlist() -> None:
    with pytest.raises(ValueError, match="outside allowed_roots"):
        FileTransactionRequest(
            operation=FileOperationKind.EXPORT,
            allowed_roots=(r"C:\exports",),
            destination_path=r"D:\other\model.dxf",
            expected_destination=_missing(r"D:\other\model.dxf"),
            expected_drawing=_drawing(),
        )


def test_close_requires_explicit_save_decision() -> None:
    with pytest.raises(ValueError, match="close_save_changes"):
        FileTransactionRequest(
            operation=FileOperationKind.CLOSE_DRAWING,
            allowed_roots=(r"C:\projects",),
            expected_drawing=_drawing(),
        )


def test_file_operations_require_idle_drawing_state() -> None:
    with pytest.raises(ValueError, match="active_command_count=0"):
        FileTransactionRequest(
            operation=FileOperationKind.SAVE_AS,
            allowed_roots=(r"C:\projects",),
            destination_path=r"C:\projects\saved.dwg",
            expected_destination=_missing(r"C:\projects\saved.dwg"),
            expected_drawing=_drawing(active_command_count=1),
        )


def test_open_requires_an_existing_digest_bound_source_snapshot() -> None:
    with pytest.raises(ValueError, match="requires expected_source"):
        FileTransactionRequest(
            operation=FileOperationKind.OPEN_DRAWING,
            allowed_roots=(r"C:\projects",),
            source_path=r"C:\projects\input.dwg",
            expected_drawing=_drawing(),
        )


def test_copy_resource_requires_distinct_source_and_destination() -> None:
    snapshot = _existing(r"C:\xicad\resource.dwg")
    with pytest.raises(ValueError, match="must differ"):
        FileTransactionRequest(
            operation=FileOperationKind.COPY_RESOURCE,
            allowed_roots=(r"C:\xicad",),
            source_path=r"C:\xicad\resource.dwg",
            destination_path=r"C:\xicad\resource.dwg",
            expected_source=snapshot,
            expected_destination=snapshot,
            overwrite_policy=OverwritePolicy.REQUIRE_MATCH,
        )
