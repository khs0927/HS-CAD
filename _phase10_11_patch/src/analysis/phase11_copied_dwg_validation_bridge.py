from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PHASE10_CONNECTOR = "PHASE10_DOMAIN_DECISION_CONNECTOR.json"


@dataclass(frozen=True)
class CopiedDwgValidationCandidate:
    candidate_id: str
    source_decision_id: str
    status: str
    original_dwg: str
    working_copy_dwg: str
    save_as_target: str
    reason: str
    blocked_reasons: list[str] = field(default_factory=list)
    execution_allowed: bool = False
    copy_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safety() -> dict[str, Any]:
    return {
        "source_mutation_allowed": False,
        "cad_execution_allowed": False,
        "zwcad_com_allowed": False,
        "sendcommand_allowed": False,
        "xicad_alias_execution_allowed": False,
        "execution_allowed": False,
        "copied_dwg_validation_only": True,
        "live_execution_allowed": False,
        "original_dwg_mutation_allowed": False,
    }


def _sha256_if_exists(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_phase11_copied_dwg_validation_bridge(
    workspace: str | Path,
    *,
    phase10_connector_path: str | Path | None = None,
    original_dwg: str | Path | None = None,
    working_copy_dwg: str | Path | None = None,
    save_as_target: str | Path | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    connector_path = Path(phase10_connector_path) if phase10_connector_path else workspace_path / DEFAULT_PHASE10_CONNECTOR
    warnings: list[str] = []

    decisions: list[dict[str, Any]] = []
    if connector_path.exists():
        connector = _load_json(connector_path)
        decisions = connector.get("domain_decision_candidates") or []
    else:
        warnings.append(f"Phase10 connector missing: {connector_path}")

    original = Path(original_dwg) if original_dwg else workspace_path / "original.dwg"
    copy = Path(working_copy_dwg) if working_copy_dwg else workspace_path / "working_copy.dwg"
    save_target = Path(save_as_target) if save_as_target else workspace_path / "safe_save_as_target.dwg"

    blocked_reasons: list[str] = []
    if original == copy:
        blocked_reasons.append("original_and_working_copy_paths_are_same")
    if original == save_target:
        blocked_reasons.append("original_and_save_as_target_paths_are_same")
    if copy == save_target:
        blocked_reasons.append("working_copy_and_save_as_target_paths_are_same")
    if not decisions:
        blocked_reasons.append("no_phase10_domain_decision_candidates")
    if not original.exists():
        blocked_reasons.append("original_dwg_not_found")
    if copy.exists() and original.exists() and _sha256_if_exists(copy) == _sha256_if_exists(original):
        copy_hash_status = "copy_matches_original"
    elif copy.exists():
        copy_hash_status = "copy_exists_but_hash_differs_or_original_missing"
    else:
        copy_hash_status = "copy_not_created_yet"

    candidates: list[CopiedDwgValidationCandidate] = []
    ready_decisions = [item for item in decisions if item.get("status") != "blocked"]
    for idx, decision in enumerate(ready_decisions or decisions or [{"decision_id": "phase10:missing"}], start=1):
        decision_blocked = [str(item) for item in (decision.get("blocked_reasons") or [])]
        all_blocked = blocked_reasons + decision_blocked
        candidates.append(
            CopiedDwgValidationCandidate(
                candidate_id=f"phase11:copy-validation:{idx}",
                source_decision_id=str(decision.get("decision_id") or f"phase10:decision:{idx}"),
                status="blocked" if all_blocked else "ready_for_copy_validation",
                original_dwg=str(original),
                working_copy_dwg=str(copy),
                save_as_target=str(save_target),
                reason="Prepare copied DWG validation plan without opening CAD or mutating drawings.",
                blocked_reasons=all_blocked,
                execution_allowed=False,
                copy_required=True,
            )
        )

    status = "ready_for_copy_validation" if any(item.status != "blocked" for item in candidates) else "blocked"
    if any(item.status == "blocked" for item in candidates) and status != "blocked":
        status = "partial"

    package = {
        "task": "phase11_copied_dwg_validation_bridge",
        "workspace": str(workspace_path),
        "generated_at": _now(),
        "status": status,
        "source_phase10_connector": str(connector_path),
        "copy_hash_status": copy_hash_status,
        "original_sha256": _sha256_if_exists(original),
        "working_copy_sha256": _sha256_if_exists(copy),
        "validation_candidates": [item.to_dict() for item in candidates],
        "copy_validation_cli_plan": {
            "mode": "plan_only",
            "recommended_cli": "zwcad-copy-scan-validate / zwcad-copy-saveas-validate",
            "execution_allowed": False,
            "zwcad_com_allowed": False,
            "sendcommand_allowed": False,
            "operator_approved": False,
            "original_dwg": str(original),
            "working_copy_dwg": str(copy),
            "save_as_target": str(save_target),
        },
        "review_checklist": [
            "Confirm original_dwg exists.",
            "Confirm working_copy_dwg is not the same path as original_dwg.",
            "Confirm save_as_target is not the same path as original_dwg.",
            "Confirm original sha256 is unchanged before/after validation.",
            "Run live ZWCAD copy validation only in a manual local environment.",
        ],
        "warnings": warnings,
        "safety": _safety(),
    }
    return package


def render_phase11_markdown(package: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Phase 11 Copied DWG Validation Bridge",
        "",
        f"- Workspace: `{package['workspace']}`",
        f"- Status: `{package['status']}`",
        f"- Copy hash status: `{package['copy_hash_status']}`",
        "",
        "## Validation Candidates",
        "",
    ]
    for item in package["validation_candidates"]:
        lines.append(
            f"- `{item['candidate_id']}` | status=`{item['status']}` | source=`{item['source_decision_id']}` | execution=`{item['execution_allowed']}`"
        )
        if item["blocked_reasons"]:
            lines.append(f"  - blocked: {', '.join(item['blocked_reasons'])}")

    lines += ["", "## CLI Plan", ""]
    for key, value in package["copy_validation_cli_plan"].items():
        lines.append(f"- `{key}`: `{value}`")

    lines += ["", "## Safety", ""]
    for key, value in package["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def write_phase11_outputs(
    workspace: str | Path,
    *,
    phase10_connector_path: str | Path | None = None,
    original_dwg: str | Path | None = None,
    working_copy_dwg: str | Path | None = None,
    save_as_target: str | Path | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    out_path = Path(out_dir) if out_dir else workspace_path
    out_path.mkdir(parents=True, exist_ok=True)

    package = build_phase11_copied_dwg_validation_bridge(
        workspace_path,
        phase10_connector_path=phase10_connector_path,
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
    )

    json_path = out_path / "PHASE11_COPIED_DWG_VALIDATION_BRIDGE.json"
    md_path = out_path / "PHASE11_COPIED_DWG_VALIDATION_BRIDGE.md"
    cli_plan_path = out_path / "PHASE11_COPY_VALIDATION_CLI_PLAN.json"

    json_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_phase11_markdown(package), encoding="utf-8")
    cli_plan_path.write_text(
        json.dumps(package["copy_validation_cli_plan"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "status": package["status"],
        "workspace": str(workspace_path),
        "out_dir": str(out_path),
        "bridge_json": str(json_path),
        "bridge_md": str(md_path),
        "cli_plan_json": str(cli_plan_path),
        "warnings": package["warnings"],
        "safety": package["safety"],
    }
