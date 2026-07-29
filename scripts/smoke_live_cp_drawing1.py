from __future__ import annotations

import json
import time

import pythoncom
import win32com.client

from xicad_mcp.live_zwcad import LiveCpExecuteRequest, LiveCpPreviewRequest, execute_live_cp, preview_live_cp


def main() -> None:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    docs = [doc for doc in app.Documents if doc.Name.casefold() == "drawing1.dwg"]
    if len(docs) != 1:
        raise RuntimeError(f"expected one Drawing1.dwg, found {len(docs)}")
    doc = docs[0]
    doc.Activate()
    before = {str(obj.Handle) for obj in doc.ModelSpace}
    center = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [1000.0, 1000.0, 0.0])
    doc.StartUndoMark()
    try:
        arc = doc.ModelSpace.AddArc(center, 500.0, 0.0, 1.5707963267948966)
    finally:
        doc.EndUndoMark()
    arc_handle = str(arc.Handle)
    preview = preview_live_cp(
        LiveCpPreviewRequest(
            document_name="Drawing1.dwg",
            arc_handle=arc_handle,
            source_policy="replace",
        )
    )
    result = execute_live_cp(LiveCpExecuteRequest(**preview))
    after = {str(obj.Handle) for obj in doc.ModelSpace}
    if arc_handle in after or result.created_handle not in after:
        raise RuntimeError("CP replacement postcondition failed")
    doc.SendCommand("_UNDO\n1\n")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        restored = {str(obj.Handle) for obj in doc.ModelSpace}
        if arc_handle in restored and result.created_handle not in restored:
            break
        time.sleep(0.2)
    else:
        raise RuntimeError("CP Undo did not restore the source arc")
    doc.SendCommand("_UNDO\n1\n")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if {str(obj.Handle) for obj in doc.ModelSpace} == before:
            break
        time.sleep(0.2)
    else:
        raise RuntimeError("CP smoke cleanup did not restore Drawing1")
    print(json.dumps({**result.model_dump(mode="json"), "undo_restored": True}, indent=2))


if __name__ == "__main__":
    main()
