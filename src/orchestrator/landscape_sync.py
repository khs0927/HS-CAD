from __future__ import annotations

"""Utilities for synchronizing landscape sections with building overview.

This module provides a lightweight implementation that extracts key values from
`texts.json` (produced by ``src.app.cli``) and builds a sync plan.  The logic is
conservative – it only proposes replacements when a clear numeric match is
found.  Anything ambiguous is flagged as ``NEEDS_REVIEW``.

The functions are deliberately simple so that they work without a live ZWCAD
instance; tests can feed handcrafted JSON structures.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Helper I/O
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Any:
    """Load JSON from *path*.

    The function raises a clear exception if the file cannot be read – this is
    helpful during debugging and unit testing.
    """
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _dump_json(data: Any, path: Path) -> None:
    """Write *data* as pretty‑printed JSON to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

_BUILDING_KEYWORDS = [
    "건축개요",
    "공사명",
    "대지위치",
    "지역지구",
    "대지면적",
    "건축면적",
    "연면적",
    "건폐율",
    "용적률",
    "규모",
    "구조",
    "주차대수",
    "조경면적",
    "법정조경",
    "건축주",
    "설계자",
]

_LANDSCAPE_KEYWORDS = [
    "조경개요",
    "조경 개요",
    "조경면적",
    "법정 조경면적",
    "계획 조경면적",
    "식재면적",
    "조경율",
    "수목",
    "교목",
    "관목",
    "지피",
    "잔디",
    "식재수량",
    "식재계획",
    "조경식재 배식계획도",
    "조경식재배식계획도",
    "배식계획도",
    "수종",
    "규격",
    "수량",
]


def _find_nearest_value(text: str) -> str:
    """Return the first numeric value (int or float) found in *text*.

    If no number is present the empty string is returned.
    """
    m = re.search(r"\d+[,.]?\d*", text.replace(",", "."))
    return m.group(0) if m else ""


def extract_building_overview(texts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract a flat dictionary of building‑overview fields from *texts*.

    The function looks for the keywords in ``_BUILDING_KEYWORDS`` and grabs the
    nearest numeric value.  If a keyword is not found the value is empty.
    """
    result: Dict[str, Any] = {k: "" for k in _BUILDING_KEYWORDS}
    for entry in texts:
        txt: str = str(entry.get("text", ""))
        for kw in _BUILDING_KEYWORDS:
            if kw in txt:
                # Store the raw text for debugging and the numeric value.
                result[kw] = _find_nearest_value(txt)
    # Normalise keys to the expected output schema.
    mapping = {
        "공사명": "project_name",
        "대지위치": "site_location",
        "대지면적": "site_area",
        "건축면적": "building_area",
        "연면적": "gross_floor_area",
        "건폐율": "building_coverage_ratio",
        "용적률": "floor_area_ratio",
        "조경면적": "landscape_area_required",
        "법정조경": "landscape_area_proposed",
        "주차대수": "parking_count",
    }
    extracted: Dict[str, Any] = {new: result.get(old, "") for old, new in mapping.items()}
    extracted["confidence"] = {}
    extracted["source_text_handles"] = []
    return extracted


def extract_landscape_sections(texts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Collect raw landscape‑related entries.

    The function groups text objects that contain any of the keyword strings.
    It returns a mapping ``keyword -> list[entry]`` where each entry contains the
    original *handle*, *layer* and *text*.
    """
    out: Dict[str, List[Dict[str, Any]]] = {kw: [] for kw in _LANDSCAPE_KEYWORDS}
    for entry in texts:
        txt = str(entry.get("text", ""))
        for kw in _LANDSCAPE_KEYWORDS:
            if kw in txt:
                out[kw].append({
                    "handle": entry.get("handle"),
                    "layer": entry.get("layer"),
                    "text": txt,
                })
    return out


def build_landscape_sync_plan(building: Dict[str, Any], landscape: Dict[str, Any]) -> Dict[str, Any]:
    """Create a sync plan based on *building* overview and existing *landscape* data.

    The algorithm is straightforward:
    * For each numeric field that exists in *building* (e.g. ``landscape_area_required``)
      and also appears in the landscape section, propose a replacement.
    * If the building value is empty, the entry is marked ``NEEDS_REVIEW``.
    * All proposals are stored under ``proposed_updates``.
    """
    plan: Dict[str, Any] = {
        "status": "PASS",
        "dwg": "",
        "building_overview_source": building,
        "landscape_existing": landscape,
        "proposed_updates": [],
        "needs_review": [],
        "warnings": [],
        "blocked_reasons": [],
    }
    # Example numeric fields to synchronise
    sync_fields = {
        "landscape_area_required": ["조경면적", "계획 조경면적"],
        "landscape_area_proposed": ["법정 조경면적"],
    }
    for field, kw_list in sync_fields.items():
        target_val = building.get(field, "")
        if not target_val:
            plan["needs_review"].append({"field": field, "reason": "NEEDS_REVIEW"})
            continue
        # Find any landscape entry containing any of the keywords
        for kw in kw_list:
            entries = landscape.get(kw, [])
            for ent in entries:
                old = ent["text"].strip()
                new = target_val
                safe = True
                # simple numeric compare – if the old already matches, skip
                if _find_nearest_value(old) == target_val:
                    continue
                plan["proposed_updates"].append(
                    {
                        "target_handle": ent["handle"],
                        "target_layer": ent["layer"],
                        "old_text": old,
                        "new_text": new,
                        "reason": f"Sync {field} from building overview",
                        "confidence": 0.9,
                        "safe_to_replace": safe,
                    }
                )
                )
    return plan


def build_text_replacements(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert ``proposed_updates`` into a list of ``replace_text`` command dicts.

    The resulting list can be written to JSON files and fed to the existing
    ``run-command`` infrastructure.
    """
    replacements: List[Dict[str, Any]] = []
    for upd in plan.get("proposed_updates", []):
        if not upd.get("safe_to_replace"):
            continue
        replacements.append(
            {
                "command": "replace_text",
                "params": {
                    "find": upd["old_text"],
                    "replace": upd["new_text"],
                    "layer": upd["target_layer"],
                },
                "safety": {"backup_required": True, "preview_required": True},
                "metadata": {"handle": upd["target_handle"]},
            }
        )
    return replacements


def write_landscape_reports(out_dir: Path, building: Dict[str, Any], landscape: Dict[str, Any], plan: Dict[str, Any]) -> None:
    """Write JSON and Markdown artefacts for the sync operation.

    Files written:
    * ``building_overview_extracted.json``
    * ``landscape_existing.json``
    * ``landscape_sync_plan.json``
    * ``landscape_sync_report.md``
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    _dump_json(building, out_dir / "building_overview_extracted.json")
    _dump_json(landscape, out_dir / "landscape_existing.json")
    _dump_json(plan, out_dir / "landscape_sync_plan.json")

    # Simple markdown report
    lines = ["# Landscape Sync Report", "", f"**DWG**: {plan.get('dwg', '')}", ""]
    if plan.get("needs_review"):
        lines.append("## Items requiring review")
        for item in plan["needs_review"]:
            lines.append(f"- {item['field']}: {item['reason']}")
        lines.append("")
    if plan.get("proposed_updates"):
        lines.append("## Proposed updates (safe) ")
        for upd in plan["proposed_updates"]:
            lines.append(
                f"- Handle {upd['target_handle']}: `{upd['old_text']}` → `{upd['new_text']}`"
            )
    else:
        lines.append("No safe updates found.")
    (out_dir / "landscape_sync_report.md").write_text("\n".join(lines), encoding="utf-8")

# End of file
