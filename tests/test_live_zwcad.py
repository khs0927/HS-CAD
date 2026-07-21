from xicad_mcp.live_zwcad import LiveWalExecuteRequest, LiveWalPreviewRequest, preview_live_wal


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
