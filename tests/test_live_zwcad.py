import pytest

from xicad_mcp.live_zwcad import (
    LiveTextCommand,
    LiveTextMutationExecuteRequest,
    LiveTextMutationPreviewRequest,
    LiveWalExecuteRequest,
    LiveWalPreviewRequest,
    execute_live_text_mutation,
    preview_live_wal,
)


def request() -> LiveWalPreviewRequest:
    return LiveWalPreviewRequest(
        document_name="Drawing1.dwg",
        wall={
            "thickness": 200.0,
            "p1": [0.0, 0.0],
            "p2": [5000.0, 0.0],
            "p3": [5000.0, 3000.0],
            "p4": [0.0, 3000.0],
        },
    )


def test_wal_fingerprint_is_bound_to_exact_request() -> None:
    preview = request()
    result = preview_live_wal(preview)
    execution = LiveWalExecuteRequest(**preview.model_dump(), approval_fingerprint=result["approval_fingerprint"])
    assert execution.approval_fingerprint == execution.expected_fingerprint()


def test_wal_fingerprint_changes_with_geometry() -> None:
    first = request()
    second = first.model_copy(update={"document_name": "Drawing2.dwg"})
    assert first.fingerprint() != second.fingerprint()


def test_text_fingerprint_is_bound_to_alias_and_expected_value() -> None:
    first = LiveTextMutationPreviewRequest(
        document_name="Drawing1.dwg",
        command_alias=LiveTextCommand.COI,
        changes=[{"handle": "A1", "expected_text": "1000", "replacement_text": "1,000"}],
    )
    second = first.model_copy(update={"command_alias": LiveTextCommand.COR})
    assert first.fingerprint() != second.fingerprint()


def test_command_specific_executor_rejects_wrong_alias_before_cad_connection() -> None:
    preview = LiveTextMutationPreviewRequest(
        document_name="Drawing1.dwg",
        command_alias=LiveTextCommand.COI,
        changes=[{"handle": "A1", "expected_text": "1000", "replacement_text": "1,000"}],
    )
    execution = LiveTextMutationExecuteRequest(
        **preview.model_dump(), approval_fingerprint=preview.fingerprint()
    )
    with pytest.raises(ValueError, match="only executes COR"):
        execute_live_text_mutation(execution, allowed_alias=LiveTextCommand.COR)
