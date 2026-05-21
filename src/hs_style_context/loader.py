from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import StyleSource


def load_json_safe(path: str | Path | None) -> tuple[dict[str, Any] | None, list[str]]:
    if not path:
        return None, ["path not provided"]
    p = Path(path)
    if not p.exists():
        return None, [f"missing file: {p}"]
    try:
        return json.loads(p.read_text(encoding="utf-8")), []
    except Exception as exc:
        return None, [f"failed to load json {p}: {exc}"]


def load_style_sources(
    local_style_sample: str | None = None,
    zium_sheet_area: str | None = None,
    active_form_sample: str | None = None,
    active_scan: str | None = None,
    reference_style_profile: str | None = None,
) -> dict[str, Any]:
    candidates = {
        "local_style_sample": local_style_sample,
        "zium_sheet_area": zium_sheet_area,
        "active_form_sample": active_form_sample,
        "active_scan": active_scan,
        "reference_style_profile": reference_style_profile,
    }
    data: dict[str, Any] = {}
    sources: list[StyleSource] = []
    warnings: list[str] = []

    for source_type, path in candidates.items():
        loaded, source_warnings = load_json_safe(path)
        if source_warnings:
            warnings.extend([f"{source_type}: {warning}" for warning in source_warnings])
        exists = bool(path and Path(path).exists())
        sources.append(
            StyleSource(
                path=str(path or ""),
                source_type=source_type,
                exists=exists,
                loaded=loaded is not None,
                warnings=source_warnings,
            )
        )
        data[source_type] = loaded

    data["_sources"] = sources
    data["_warnings"] = warnings
    return data
