from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_state import AgentRunState
from .tool_decision_engine import ToolDecision


def write_route_report(state: AgentRunState, decision: ToolDecision, out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    payload = {"state": state.to_dict(), "decision": decision.to_dict()}

    json_path = out / "hscad_agent_route.json"
    md_path = out / "hscad_agent_route.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(to_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def to_markdown(payload: dict[str, Any]) -> str:
    context = payload["state"]["context"]
    decision = payload["decision"]
    lines = [
        "# HS-CAD Intelligent Agent Route",
        "",
        f"- Task: {context['task']}",
        f"- Primary process: {decision['primary_process']}",
        "",
        "## Selected Safe Tools",
        "| # | Tool | Command | Safety | Reason |",
        "|---:|---|---|---|---|",
    ]

    for idx, step in enumerate(decision["selected_tools"], start=1):
        lines.append(f"| {idx} | {step.get('tool', '')} | `{step.get('command', '')}` | {step.get('safety_class', '')} | {step.get('reason', '')} |")

    lines += ["", "## Held / Review-Gated Tools", "| # | Tool | Command | Safety | Reason |", "|---:|---|---|---|---|"]
    for idx, step in enumerate(decision["held_tools"], start=1):
        lines.append(f"| {idx} | {step.get('tool', '')} | `{step.get('command', '')}` | {step.get('safety_class', '')} | {step.get('safety_reason', '')} |")

    if decision["warnings"]:
        lines += ["", "## Warnings"]
        lines.extend(f"- {item}" for item in decision["warnings"])

    if decision["missing_context"]:
        lines += ["", "## Missing Context"]
        lines.extend(f"- {item}" for item in decision["missing_context"])

    lines += ["", "## Decision Trace"]
    for trace in payload["state"]["traces"]:
        lines.append(f"- **{trace['stage']}**: {trace['message']} {trace.get('data', {})}")

    return "\n".join(lines) + "\n"
