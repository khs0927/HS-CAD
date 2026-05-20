from __future__ import annotations

from pathlib import Path
from typing import Any

from src.integrations.xicad_paths import detect_xicad_profile
from src.reports.architecture_report import build_environment_snapshot
from src.reports.json_exporter import export_json
from src.scanners.block_scanner import block_summary
from src.scanners.layer_scanner import layer_counts
from src.scanners.text_scanner import extract_texts


def collect_debug_bundle(adapter: Any | None, dwg: str | None, xicad_root: str | None, out_dir: str | Path, max_objects: int = 200) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    env = build_environment_snapshot()
    paths["environment"] = export_json(env, out / "environment.json")

    xicad_data: dict[str, Any] = {"provided_root": xicad_root, "detected": False}
    if xicad_root:
        try:
            profile = detect_xicad_profile(xicad_root)
            xicad_data = profile.to_dict() | {"detected": True}
        except Exception as exc:
            xicad_data["error"] = str(exc)
    paths["xicad_detection"] = export_json(xicad_data, out / "xicad_detection.json")

    objects: list[dict[str, Any]] = []
    connection: dict[str, Any] = {"dwg": dwg, "connected": False}
    if adapter is not None:
        try:
            objects = adapter.scan_modelspace()
            connection["connected"] = True
            connection["object_count"] = len(objects)
            connection["warnings"] = getattr(adapter, "warnings", [])
        except Exception as exc:
            connection["error"] = str(exc)
    paths["zwcad_connection"] = export_json(connection, out / "zwcad_connection.json")
    sample = objects[:max_objects]
    paths["scan_sample"] = export_json(sample, out / "scan_sample.json")
    paths["layers"] = export_json(layer_counts(objects), out / "layers.json")
    paths["blocks"] = export_json({k: v for k, v in block_summary(objects).items()}, out / "blocks.json")
    paths["texts"] = export_json(extract_texts(objects)[:max_objects], out / "texts.json")
    capabilities = {
        "adapter_methods": sorted([name for name in dir(adapter) if not name.startswith("_")]) if adapter is not None else [],
        "supported_without_zwcad": ["command_validation", "xicad_catalog", "xicad_safe_plan", "architecture_static_analysis", "public_release_packaging"],
    }
    paths["command_capabilities"] = export_json(capabilities, out / "command_capabilities.json")
    summary = ["# Debug Bundle Summary", "", f"- DWG: {dwg}", f"- ZWCAD connected: {connection.get('connected')}", f"- Object count: {connection.get('object_count', 0)}", f"- XiCAD root: {xicad_root}", f"- XiCAD detected: {xicad_data.get('detected')}", ""]
    if connection.get("error"):
        summary.append(f"- ZWCAD error: {connection['error']}")
    if xicad_data.get("error"):
        summary.append(f"- XiCAD error: {xicad_data['error']}")
    (out / "debug_summary.md").write_text("\n".join(summary), encoding="utf-8")
    paths["debug_summary"] = out / "debug_summary.md"
    warnings = ["# Warnings", "", *[f"- {w}" for w in connection.get("warnings", [])]]
    (out / "warnings.md").write_text("\n".join(warnings), encoding="utf-8")
    paths["warnings"] = out / "warnings.md"
    return paths
