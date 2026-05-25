from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PHASE11_PLAN = "PHASE11_COPY_VALIDATION_CLI_PLAN.json"
DEFAULT_ALLOWLIST_PLAN = "XICAD_ALIAS_ALLOWLIST_PLAN.json"


@dataclass(frozen=True)
class Phase12LiveExecutionCandidate:
    candidate_id: str
    source_plan: str
    status: str
    alias: str
    original_dwg: str
    working_copy_dwg: str
    save_as_target: str
    execution_mode: str
    review_required: bool = True
    operator_approved: bool = False
    execution_allowed: bool = False
    sendcommand_allowed: bool = False
    blocked_reasons: list[str] = field(default_factory=list)
    required_checks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_if_exists(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _safety(*, manual_live_candidate: bool = False) -> dict[str, Any]:
    return {
        "source_mutation_allowed": False,
        "original_dwg_mutation_allowed": False,
        "cad_execution_allowed_by_default": False,
        "zwcad_com_allowed_by_default": False,
        "sendcommand_allowed_by_default": False,
        "xicad_alias_execution_allowed_by_default": False,
        "manual_live_candidate": manual_live_candidate,
        "requires_copied_dwg": True,
        "requires_allowlist_alias": True,
        "requires_operator_approval": True,
        "requires_live_flag": True,
        "execution_allowed": False,
    }


def build_phase12_manual_live_execution_candidate(
    workspace: str | Path,
    *,
    phase11_plan_path: str | Path | None = None,
    allowlist_plan_path: str | Path | None = None,
    alias: str = "WAL",
    manual_live_flag: bool = False,
    operator_approved: bool = False,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    phase11_path = Path(phase11_plan_path) if phase11_plan_path else workspace_path / DEFAULT_PHASE11_PLAN
    allowlist_path = Path(allowlist_plan_path) if allowlist_plan_path else workspace_path / DEFAULT_ALLOWLIST_PLAN

    warnings: list[str] = []
    blocked: list[str] = []

    phase11 = _load_json_if_exists(phase11_path)
    allowlist = _load_json_if_exists(allowlist_path)

    if not phase11:
        blocked.append("missing_phase11_copy_validation_cli_plan")
        warnings.append(f"Phase11 copy validation CLI plan missing: {phase11_path}")

    if not allowlist:
        blocked.append("missing_xicad_alias_allowlist_plan")
        warnings.append(f"XiCAD alias allowlist plan missing: {allowlist_path}")

    original = Path(str(phase11.get("original_dwg") or workspace_path / "original.dwg"))
    working_copy = Path(str(phase11.get("working_copy_dwg") or workspace_path / "working_copy.dwg"))
    save_target = Path(str(phase11.get("save_as_target") or workspace_path / "safe_save_as_target.dwg"))

    if original == working_copy:
        blocked.append("original_and_working_copy_paths_are_same")
    if original == save_target:
        blocked.append("original_and_save_as_target_paths_are_same")
    if working_copy == save_target:
        blocked.append("working_copy_and_save_as_target_paths_are_same")

    if not original.exists():
        blocked.append("original_dwg_not_found")
    if not working_copy.exists():
        blocked.append("working_copy_dwg_not_found")

    allow_aliases = set(str(item).upper() for item in (allowlist.get("dry_run_allowed_aliases") or []))
    blocked_aliases = set(str(item).upper() for item in (allowlist.get("blocked_aliases") or []))
    execution_aliases = set(str(item).upper() for item in (allowlist.get("execution_allowed_aliases") or []))

    alias_upper = alias.upper().strip()
    if alias_upper in blocked_aliases:
        blocked.append("alias_is_blocked_by_allowlist")
    if alias_upper not in allow_aliases:
        blocked.append("alias_not_in_dry_run_allowlist")
    if execution_aliases:
        blocked.append("allowlist_execution_allowed_aliases_must_be_empty_before_manual_live_stage")

    if not manual_live_flag:
        blocked.append("manual_live_flag_not_enabled")
    if not operator_approved:
        blocked.append("operator_not_approved")

    original_hash = _sha256_if_exists(original)
    working_hash = _sha256_if_exists(working_copy)
    if original_hash and working_hash and original_hash != working_hash:
        # A copied DWG may diverge later; for pre-execution candidate, we prefer an unmodified copy.
        blocked.append("working_copy_hash_differs_from_original_before_execution")

    candidate_status = "manual_ready_candidate" if not blocked else "blocked"

    candidate = Phase12LiveExecutionCandidate(
        candidate_id="phase12:manual-live-execution-candidate:1",
        source_plan=str(phase11_path),
        status=candidate_status,
        alias=alias_upper,
        original_dwg=str(original),
        working_copy_dwg=str(working_copy),
        save_as_target=str(save_target),
        execution_mode="manual_live_candidate_only",
        review_required=True,
        operator_approved=operator_approved,
        execution_allowed=(candidate_status == "manual_ready_candidate"),
        sendcommand_allowed=(candidate_status == "manual_ready_candidate"),
        blocked_reasons=sorted(set(blocked)),
        required_checks=[
            "original_dwg_hash_recorded",
            "working_copy_is_distinct_path",
            "save_as_target_is_distinct_path",
            "alias_in_allowlist",
            "operator_approved_true",
            "manual_live_flag_true",
            "execution_now_allowed_by_final_runner",
        ],
    )

    package = {
        "task": "phase12_manual_live_execution_candidate",
        "workspace": str(workspace_path),
        "generated_at": _now(),
        "status": candidate_status,
        "source_phase11_plan": str(phase11_path),
        "source_allowlist_plan": str(allowlist_path),
        "candidate": candidate.to_dict(),
        "hashes": {
            "original_sha256": original_hash,
            "working_copy_sha256": working_hash,
        },
        "final_runner_note": (
            "This package is not a runner. It only proves that all preconditions for a manual live execution candidate "
            "were reviewed. A separate final runner must still refuse execution by default."
        ),
        "warnings": warnings,
        "safety": _safety(manual_live_candidate=candidate_status == "manual_ready_candidate"),
    }
    return package


def render_phase12_markdown(package: dict[str, Any]) -> str:
    candidate = package["candidate"]
    lines = [
        "# HS-CAD Phase 12 Manual Live Execution Candidate",
        "",
        f"- Workspace: `{package['workspace']}`",
        f"- Status: `{package['status']}`",
        f"- Alias: `{candidate['alias']}`",
        f"- Original DWG: `{candidate['original_dwg']}`",
        f"- Working copy DWG: `{candidate['working_copy_dwg']}`",
        f"- SaveAs target: `{candidate['save_as_target']}`",
        "",
        "## Candidate State",
        "",
        f"- Operator approved: `{candidate['operator_approved']}`",
        f"- Execution allowed: `{candidate['execution_allowed']}`",
        f"- SendCommand allowed: `{candidate['sendcommand_allowed']}`",
        "",
        "## Blocked Reasons",
        "",
    ]
    if candidate["blocked_reasons"]:
        lines.extend(f"- {reason}" for reason in candidate["blocked_reasons"])
    else:
        lines.append("- None, but this is still only a manual-ready candidate; it does not execute.")

    lines += ["", "## Safety", ""]
    for key, value in package["safety"].items():
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines).rstrip() + "\n"


def write_phase12_outputs(
    workspace: str | Path,
    *,
    phase11_plan_path: str | Path | None = None,
    allowlist_plan_path: str | Path | None = None,
    alias: str = "WAL",
    manual_live_flag: bool = False,
    operator_approved: bool = False,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    out_path = Path(out_dir) if out_dir else workspace_path
    out_path.mkdir(parents=True, exist_ok=True)

    package = build_phase12_manual_live_execution_candidate(
        workspace_path,
        phase11_plan_path=phase11_plan_path,
        allowlist_plan_path=allowlist_plan_path,
        alias=alias,
        manual_live_flag=manual_live_flag,
        operator_approved=operator_approved,
    )

    json_path = out_path / "PHASE12_MANUAL_LIVE_EXECUTION_CANDIDATE.json"
    md_path = out_path / "PHASE12_MANUAL_LIVE_EXECUTION_CANDIDATE.md"
    final_guard_path = out_path / "PHASE12_FINAL_RUNNER_GUARD.json"

    json_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_phase12_markdown(package), encoding="utf-8")
    final_guard_path.write_text(
        json.dumps(
            {
                "status": "not_implemented",
                "message": "Final live runner is intentionally not implemented in this patch.",
                "must_require_manual_flag": True,
                "must_require_operator_approval": True,
                "must_require_copied_dwg": True,
                "must_refuse_original_dwg": True,
                "must_refuse_unknown_alias": True,
                "must_refuse_blocked_alias": True,
                "must_default_to_no_sendcommand": True,
                "safety": package["safety"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "status": package["status"],
        "workspace": str(workspace_path),
        "out_dir": str(out_path),
        "candidate_json": str(json_path),
        "candidate_md": str(md_path),
        "final_runner_guard": str(final_guard_path),
        "warnings": package["warnings"],
        "safety": package["safety"],
    }
