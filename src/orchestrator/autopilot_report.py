from __future__ import annotations

from pathlib import Path
from typing import Any
import json


def write_autopilot_outputs(payload: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    plan_path = out / "autopilot_plan.json"
    result_path = out / "autopilot_result.json"
    md_path = out / "autopilot_report.md"

    plan_path.write_text(json.dumps(payload.get("plan", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_autopilot_markdown(payload), encoding="utf-8")
    return {"plan": str(plan_path), "result": str(result_path), "markdown": str(md_path)}


def render_autopilot_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD Autopilot Report",
        "",
        f"- Task: {payload.get('task', '')}",
        f"- Mode: {payload.get('mode', '')}",
        f"- Run safe: {payload.get('run_safe', False)}",
        "",
        "## Executed Steps",
        "| Step | Status | Output |",
        "|---|---|---|",
    ]
    for step in payload.get("executed_steps", []):
        lines.append(f"| {step.get('name')} | {step.get('status')} | {step.get('output', '')} |")

    lines += ["", "## Held Steps", "| Step | Reason |", "|---|---|"]
    for step in payload.get("held_steps", []):
        lines.append(f"| {step.get('name')} | {step.get('reason')} |")

    lines += ["", "## Warnings"]
    warnings = payload.get("warnings", [])
    if warnings:
        lines += [f"- {warning}" for warning in warnings]
    else:
        lines.append("- None")

    lines += [
        "",
        "## Safety",
        "- Autopilot does not execute drawing mutation commands.",
        "- Autopilot does not modify xicad_recipe_registry.py.",
        "- Save/Delete/Explode/Purge/SendCommand steps are held for review.",
    ]
    return "\n".join(lines) + "\n"
