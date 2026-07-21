from __future__ import annotations

import json
import time

import win32com.client

from xicad_mcp.live_zwcad import (
    LiveTextCommand,
    LiveTextMutationExecuteRequest,
    LiveTextMutationPreviewRequest,
    execute_live_text_mutation,
    preview_live_text_mutation,
)


def main() -> None:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    documents = [doc for doc in app.Documents if doc.Name.casefold() == "drawing1.dwg"]
    if len(documents) != 1:
        raise RuntimeError(f"expected one Drawing1.dwg, found {len(documents)}")
    doc = documents[0]
    doc.Activate()
    before = {str(obj.Handle) for obj in doc.ModelSpace}
    aliases = (
        LiveTextCommand.TD,
        LiveTextCommand.TM,
        LiveTextCommand.PY,
        LiveTextCommand.M2,
        LiveTextCommand.INA,
        LiveTextCommand.SPN,
        LiveTextCommand.LIS,
        LiveTextCommand.LMA,
        LiveTextCommand.LNA,
        LiveTextCommand.QD,
        LiveTextCommand.NUMC,
        LiveTextCommand.TIE,
        LiveTextCommand.TII,
    )
    results = []
    for index, alias in enumerate(aliases):
        preview = LiveTextMutationPreviewRequest(
            document_name="Drawing1.dwg",
            command_alias=alias,
            create_specs=[
                {
                    "text": f"{alias.value}-HEADLESS",
                    "insertion_point": {"x": index * 500.0, "y": 4000.0, "z": 0.0},
                    "layer": "0",
                    "text_style": "Standard",
                    "text_height": 100.0,
                    "rotation_degrees": 0.0,
                }
            ],
        )
        fingerprint = preview_live_text_mutation(preview)["approval_fingerprint"]
        execution = LiveTextMutationExecuteRequest(
            **preview.model_dump(), approval_fingerprint=fingerprint
        )
        result = execute_live_text_mutation(execution, allowed_alias=alias)
        if len(result.created_handles) != 1:
            raise RuntimeError(f"{alias} did not create exactly one text entity")
        results.append(result.model_dump(mode="json"))
        doc.SendCommand("_UNDO\n1\n")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if {str(obj.Handle) for obj in doc.ModelSpace} == before:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError(f"{alias} Undo did not restore Drawing1")
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
