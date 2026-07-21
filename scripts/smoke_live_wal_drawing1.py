from __future__ import annotations

import json
import time

import win32com.client

from xicad_mcp.live_zwcad import (
    LiveWalExecuteRequest,
    LiveWalPreviewRequest,
    execute_live_wal,
    preview_live_wal,
)


def main() -> None:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    documents = [doc for doc in app.Documents if doc.Name.casefold() == "drawing1.dwg"]
    if len(documents) != 1:
        raise RuntimeError(f"expected one Drawing1.dwg, found {len(documents)}")
    doc = documents[0]
    doc.Activate()
    before = {str(obj.Handle) for obj in doc.ModelSpace}
    preview = LiveWalPreviewRequest(
        document_name="Drawing1.dwg",
        wall={
            "thickness": 200.0,
            "p1": [0.0, 0.0],
            "p2": [5000.0, 0.0],
            "p3": [5000.0, 3000.0],
            "p4": [0.0, 3000.0],
        },
    )
    approval = preview_live_wal(preview)["approval_fingerprint"]
    result = execute_live_wal(
        LiveWalExecuteRequest(**preview.model_dump(), approval_fingerprint=approval)
    )
    after = {str(obj.Handle) for obj in doc.ModelSpace}
    if not set(result.created_handles) <= after:
        raise RuntimeError("created WAL handles were not found after execution")

    doc.SendCommand("_UNDO\n1\n")
    deadline = time.monotonic() + 10
    restored: set[str] = set()
    while time.monotonic() < deadline:
        restored = {str(obj.Handle) for obj in doc.ModelSpace}
        if restored == before:
            break
        time.sleep(0.2)
    if restored != before:
        raise RuntimeError(f"Undo did not restore Drawing1: before={len(before)}, restored={len(restored)}")
    print(
        json.dumps(
            {
                **result.model_dump(mode="json"),
                "undo_restored": True,
                "restored_count": len(restored),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
