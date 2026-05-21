from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def prepare_image_result_fit(
    recognition_output: Path,
    out_dir: Path,
    *,
    target_active: bool = False,
    base_point: str | None = None,
    scale: float = 1.0,
    rotation: float = 0.0,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(str(path) for path in recognition_output.glob("**/*") if path.is_file()) if recognition_output.exists() else []
    payload = {
        "recognition_output": str(recognition_output),
        "files": files,
        "target_active": target_active,
        "base_point": base_point,
        "scale": scale,
        "rotation": rotation,
        "status": "prepared_only_no_insert",
        "notes": [
            "No active drawing insert is performed unless a later implementation explicitly adds it.",
            "Use this report to align recognition outputs with the active drawing layer standard.",
        ],
    }
    path = out_dir / "image_result_fit_report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"report": str(path), "file_count": len(files), "status": payload["status"]}
