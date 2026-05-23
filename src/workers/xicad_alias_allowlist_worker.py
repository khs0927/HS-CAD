from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.execution.xicad_alias_plan import build_xicad_alias_allowlist_plan
from src.reports.json_exporter import export_json


def load_command_plan(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Command plan must be a JSON object: {path}")
    if "dry_run_steps" not in data:
        raise ValueError(f"Command plan is missing dry_run_steps: {path}")
    return data


def render_alias_allowlist_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD XiCAD Alias Allowlist Plan",
        "",
        f"- Source command plan: {plan.get('source_command_plan')}",
        f"- Status: {plan.get('status')}",
        "",
        "## Dry-run allowed aliases",
    ]
    for alias in plan.get("dry_run_allowed_aliases") or []:
        lines.append(f"- {alias}")

    lines += ["", "## Review required aliases"]
    for alias in plan.get("review_required_aliases") or []:
        lines.append(f"- {alias}")

    lines += ["", "## Blocked aliases"]
    for alias in plan.get("blocked_aliases") or []:
        lines.append(f"- {alias}")

    lines += ["", "## Steps"]
    for step in plan.get("steps") or []:
        cls = step.get("classification") or {}
        policy = cls.get("policy") or {}
        lines.append(
            f"- #{step.get('order')} {cls.get('alias')} | risk={policy.get('risk')} | dry_run={cls.get('allowed_for_dry_run')} | execution={cls.get('allowed_for_execution')}"
        )
        if cls.get("blocked_reason"):
            lines.append(f"  - Blocked: {cls.get('blocked_reason')}")

    lines += [
        "",
        "## Safety",
        "- This plan does not execute XiCAD aliases.",
        "- Unknown aliases are blocked.",
        "- Destructive aliases are blocked.",
        "- Execution allowed aliases should remain empty until a later approved-copy execution stage.",
    ]

    return "\n".join(lines).rstrip() + "\n"


def run_xicad_alias_allowlist_worker(
    command_plan_json: str | Path,
    *,
    out_dir: str | Path = "outputs/xicad_alias_allowlist",
) -> dict[str, Any]:
    command_plan = load_command_plan(command_plan_json)
    plan = build_xicad_alias_allowlist_plan(command_plan, source_command_plan=str(command_plan_json))

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    plan_json = out / "XICAD_ALIAS_ALLOWLIST_PLAN.json"
    report_md = out / "XICAD_ALIAS_ALLOWLIST_PLAN.md"

    payload = plan.to_dict()
    export_json(payload, plan_json)
    report_md.write_text(render_alias_allowlist_markdown(payload), encoding="utf-8")

    return {
        "out_dir": str(out),
        "plan_json": str(plan_json),
        "report": str(report_md),
        "status": plan.status,
        "blocked_count": len(plan.blocked_aliases),
        "dry_run_allowed_count": len(plan.dry_run_allowed_aliases),
        "execution_allowed_count": len(plan.execution_allowed_aliases),
    }
