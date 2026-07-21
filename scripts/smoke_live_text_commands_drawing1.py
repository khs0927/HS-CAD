from __future__ import annotations

import json
import time

import pythoncom
import win32com.client

from xicad_mcp.live_zwcad import (
    LiveTextCommand,
    LiveTextMutationExecuteRequest,
    LiveTextMutationPreviewRequest,
    execute_live_text_mutation,
    preview_live_text_mutation,
)


def _point(x: float, y: float) -> object:
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [x, y, 0.0])


def _undo_and_wait(doc: object, expected_text: str, handle: str, expected_height: float = 100.0) -> None:
    doc.SendCommand("_UNDO\n1\n")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        obj = next(item for item in doc.ModelSpace if str(item.Handle) == handle)
        if str(obj.TextString) == expected_text and abs(float(obj.Height) - expected_height) < 1e-9:
            return
        time.sleep(0.2)
    raise RuntimeError(f"Undo failed to restore text handle {handle}")


def main() -> None:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    documents = [doc for doc in app.Documents if doc.Name.casefold() == "drawing1.dwg"]
    if len(documents) != 1:
        raise RuntimeError(f"expected one Drawing1.dwg, found {len(documents)}")
    doc = documents[0]
    doc.Activate()
    before_handles = {str(obj.Handle) for obj in doc.ModelSpace}

    cases = [
        (LiveTextCommand.COI, "1000", "1,000", None),
        (LiveTextCommand.COR, "1,000", "1000", None),
        (LiveTextCommand.NUC, "25", "50", None),
        (LiveTextCommand.FAR, "OLD-WALL", "NEW-WALL", None),
        (LiveTextCommand.TAP, "ROOM", "[ROOM]-A", None),
        (LiveTextCommand.TS, "HEIGHT", None, 250.0),
    ]
    results = []
    doc.StartUndoMark()
    created = []
    try:
        for index, (_alias, original, _replacement, _height) in enumerate(cases):
            created.append(doc.ModelSpace.AddText(original, _point(index * 1000.0, 0.0), 100.0))
    finally:
        doc.EndUndoMark()

    try:
        for entity, (alias, original, replacement, replacement_height) in zip(created, cases, strict=True):
            handle = str(entity.Handle)
            if replacement_height is None:
                preview = LiveTextMutationPreviewRequest(
                    document_name="Drawing1.dwg",
                    command_alias=alias,
                    changes=[
                        {
                            "handle": handle,
                            "expected_text": original,
                            "replacement_text": replacement,
                        }
                    ],
                )
            else:
                preview = LiveTextMutationPreviewRequest(
                    document_name="Drawing1.dwg",
                    command_alias=alias,
                    height_changes=[
                        {
                            "handle": handle,
                            "expected_height": 100.0,
                            "replacement_height": replacement_height,
                        }
                    ],
                )
            fingerprint = preview_live_text_mutation(preview)["approval_fingerprint"]
            execution = LiveTextMutationExecuteRequest(
                **preview.model_dump(), approval_fingerprint=fingerprint
            )
            result = execute_live_text_mutation(execution, allowed_alias=alias)
            results.append(result.model_dump(mode="json"))
            _undo_and_wait(doc, original, handle)
    finally:
        doc.SendCommand("_UNDO\n1\n")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if {str(obj.Handle) for obj in doc.ModelSpace} == before_handles:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("test text cleanup Undo did not restore Drawing1")

    print(
        json.dumps(
            {
                "document": doc.Name,
                "commands": results,
                "undo_restored": True,
                "final_object_count": len(doc.ModelSpace),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
