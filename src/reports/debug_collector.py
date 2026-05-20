from __future__ import annotations

import importlib.util
import platform
import sys
from pathlib import Path
from typing import Any

from src.integrations.xicad_paths import detect_xicad_profile
from src.reports.json_exporter import export_json


def _can_import(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def collect_environment(xicad_root: str | None = None) -> dict[str, Any]:
    xicad = detect_xicad_profile(xicad_root).to_dict() if xicad_root else None
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "working_directory": str(Path.cwd()),
        "package_version": "0.1.0",
        "imports": {
            "comtypes": _can_import("comtypes"),
            "pywin32": _can_import("win32com.client"),
            "ezdxf": _can_import("ezdxf"),
            "cad_pyrx": _can_import("pyrx") or _can_import("cad_pyrx"),
            "pandas": _can_import("pandas"),
            "openpyxl": _can_import("openpyxl"),
        },
        "xicad_detection": xicad,
    }


def write_debug_bundle(
    out_dir: str | Path,
    environment: dict[str, Any],
    zwcad_connection: dict[str, Any],
    xicad_detection: dict[str, Any] | None,
    objects: list[dict[str, Any]],
    layers: list[str],
    blocks: list[str],
    texts: list[dict[str, Any]],
    capabilities: dict[str, Any],
    warnings: list[str],
    max_objects: int = 200,
) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    export_json(environment, out / "environment.json")
    export_json(zwcad_connection, out / "zwcad_connection.json")
    export_json(xicad_detection or {}, out / "xicad_detection.json")
    export_json(objects[:max_objects], out / "scan_sample.json")
    export_json(layers, out / "layers.json")
    export_json(blocks, out / "blocks.json")
    export_json(texts, out / "texts.json")
    export_json(capabilities, out / "command_capabilities.json")
    (out / "warnings.md").write_text("\n".join(f"- {w}" for w in warnings) or "- None\n", encoding="utf-8")
    (out / "debug_summary.md").write_text(
        "# Debug Bundle\n\n"
        f"- Objects sampled: {min(len(objects), max_objects)} / {len(objects)}\n"
        f"- Layers: {len(layers)}\n"
        f"- Blocks: {len(blocks)}\n"
        f"- Texts: {len(texts)}\n"
        f"- ZWCAD connected: {zwcad_connection.get('connected')}\n"
        f"- Warning count: {len(warnings)}\n",
        encoding="utf-8",
    )
    return out
