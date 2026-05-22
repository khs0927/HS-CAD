from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agent_state import AgentRunState, normalize_context
from .route_report import write_route_report
from .tool_decision_engine import ToolDecision, ToolDecisionEngine


@dataclass
class IntelligentRouteResult:
    decision: ToolDecision
    report_paths: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {"decision": self.decision.to_dict(), "report_paths": self.report_paths}


def build_intelligent_route(
    task: str,
    *,
    has_image: bool = False,
    has_pdf: bool = False,
    has_dwg: bool = False,
    has_active_drawing: bool = False,
    wants_write: bool = False,
    image_path: str | Path | None = None,
    dwg_path: str | Path | None = None,
    out_dir: str | Path = "outputs/agent_route",
) -> IntelligentRouteResult:
    context = normalize_context(
        task,
        has_image=has_image,
        has_pdf=has_pdf,
        has_dwg=has_dwg,
        has_active_drawing=has_active_drawing,
        wants_write=wants_write,
        image_path=image_path,
        dwg_path=dwg_path,
        out_dir=out_dir,
    )
    state = AgentRunState(context=context)
    state.add_trace("intake", "Normalized user task context.", **context.to_dict())

    engine = ToolDecisionEngine()
    decision = engine.decide(state)
    paths = write_route_report(state, decision, out_dir)
    return IntelligentRouteResult(decision=decision, report_paths=paths)
