from __future__ import annotations

import json
from pathlib import Path

from src.analysis.dxf_delta_extractor import DXFDeltaReport, DXFEntityModification
from src.execution.xicad_signature_validator import validate_signature


def run_signature_validator_worker(
    seeds_json_path: str,
    delta_json_path: str,
    out_dir: str,
) -> dict:
    """
    Worker that matches an extracted sandbox Delta against a configured Seed.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    with open(seeds_json_path, "r", encoding="utf-8") as f:
        seeds_data = json.load(f)

    with open(delta_json_path, "r", encoding="utf-8") as f:
        delta_data = json.load(f)

    # Reconstruct DXFDeltaReport from dict
    # Extract modified
    modified_objs = []
    for m in delta_data.get("modified", []):
        modified_objs.append(
            DXFEntityModification(
                handle=m.get("handle", ""),
                old_state=m.get("old_state", {}),
                new_state=m.get("new_state", {}),
                changed_keys=m.get("changed_keys", []),
            )
        )

    delta = DXFDeltaReport(
        command_hint=delta_data.get("command_hint", "unknown"),
        added_count=delta_data.get("added_count", 0),
        deleted_count=delta_data.get("deleted_count", 0),
        modified_count=delta_data.get("modified_count", 0),
        added=delta_data.get("added", []),
        deleted=delta_data.get("deleted", []),
        modified=modified_objs,
    )

    alias = delta.command_hint
    target_seed = next((s for s in seeds_data.get("seeds", []) if s.get("alias") == alias), None)

    if not target_seed:
        return {"error": f"No seed found for alias '{alias}' in {seeds_json_path}"}

    validation_result = validate_signature(target_seed, delta)

    # Load existing verified signatures if any
    verified_file = out / "VERIFIED_XICAD_SIGNATURES.json"
    existing_data = {"verified_signatures": []}
    if verified_file.exists():
        with open(verified_file, "r", encoding="utf-8") as f:
            existing_data = json.load(f)

    # Upsert the result
    filtered_sigs = [s for s in existing_data["verified_signatures"] if s.get("alias") != alias]
    filtered_sigs.append(validation_result)
    existing_data["verified_signatures"] = filtered_sigs

    with open(verified_file, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, indent=2, ensure_ascii=False)

    return validation_result
