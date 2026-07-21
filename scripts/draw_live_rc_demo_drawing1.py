from __future__ import annotations

import json

import win32com.client

from xicad_mcp.live_zwcad import LiveRcExecuteRequest, LiveRcPreviewRequest, execute_live_rc, preview_live_rc


def main() -> None:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    doc = next(doc for doc in app.Documents if doc.Name.casefold() == "drawing1.dwg")
    doc.Activate()
    sources = []
    for obj in doc.ModelSpace:
        name = str(obj.ObjectName).casefold()
        if "polyline" in name and not sources:
            sources.append(str(obj.Handle))
        elif "text" in name and str(obj.TextString) == "HS-CAD xiCAD MCP LIVE DEMO":
            sources.append(str(obj.Handle))
    if len(sources) != 2:
        raise RuntimeError(f"expected demo wall and title, found handles {sources}")
    preview_request = LiveRcPreviewRequest(
        document_name="Drawing1.dwg",
        source_handles=sources,
        base_point=(3000.0, 2000.0, 0.0),
        angle_degrees=15.0,
        copies=2,
    )
    preview = preview_live_rc(preview_request)
    result = execute_live_rc(LiveRcExecuteRequest(**preview))
    doc.Regen(1)
    app.ZoomExtents()
    print(json.dumps({**result.model_dump(mode="json"), "undo_performed": False}, indent=2))


if __name__ == "__main__":
    main()
