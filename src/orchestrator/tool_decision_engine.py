from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .agent_state import AgentRunState
from .execution_policy import StepSafety, classify_command_safety
from .intent_model import AgentIntent, classify_agent_intent

try:
    from .workflow_planner import plan_hscad_workflow
except Exception:  # compatibility fallback
    plan_hscad_workflow = None  # type: ignore


@dataclass
class ToolDecision:
    primary_process: str
    selected_tools: list[dict[str, Any]]
    held_tools: list[dict[str, Any]]
    safety: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)
    missing_context: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolDecisionEngine:
    """Reasoning layer that chooses tools without mutating drawings."""

    def decide(self, state: AgentRunState) -> ToolDecision:
        context = state.context
        intent = classify_agent_intent(context)
        state.add_trace("intent", f"Classified task as {intent.value}")

        if plan_hscad_workflow is not None:
            plan = plan_hscad_workflow(
                context.task,
                has_image=context.has_image,
                has_dwg=context.has_dwg,
                wants_write=context.wants_write,
            )
            raw_steps = [step.to_dict() for step in plan.steps]
            warnings = list(getattr(plan, "warnings", []))
            missing = list(getattr(plan, "missing_context", []))
            state.add_trace("workflow_planner", "Existing workflow planner produced ordered steps.", step_count=len(raw_steps))
        else:
            raw_steps = self._fallback_steps(intent)
            warnings = ["workflow_planner unavailable; used fallback process."]
            missing = []
            state.add_trace("workflow_planner", "Used fallback ordered steps.", step_count=len(raw_steps))

        safety_results: list[StepSafety] = []
        selected: list[dict[str, Any]] = []
        held: list[dict[str, Any]] = []

        for step in raw_steps:
            command = str(step.get("command", ""))
            safety = classify_command_safety(command, wants_write=context.wants_write)
            safety_results.append(safety)
            enriched = dict(step)
            enriched["safety_class"] = safety.safety_class.value
            enriched["safe_to_run"] = safety.safe_to_run
            enriched["safety_reason"] = safety.reason
            if safety.safe_to_run:
                selected.append(enriched)
            else:
                held.append(enriched)

        if context.has_image and not context.image_path:
            missing.append("Image/PDF task detected, but no image path was provided. Synthetic mode may be used for self-test.")
        if context.has_dwg and not context.dwg_path and not context.has_active_drawing:
            missing.append("DWG task detected, but no DWG path or active drawing flag was provided.")
        if context.wants_write:
            warnings.append("Write intent detected. Mutation-capable steps are review-gated and not auto-run.")

        state.add_trace("safety_gate", "Classified selected and held tools.", selected=len(selected), held=len(held))

        return ToolDecision(
            primary_process=intent.value,
            selected_tools=selected,
            held_tools=held,
            safety=[item.to_dict() for item in safety_results],
            warnings=warnings,
            missing_context=missing,
        )

    def _fallback_steps(self, intent: AgentIntent) -> list[dict[str, Any]]:
        mapping = {
            AgentIntent.FLOORPLAN_TO_CAD: [
                {"order": 1, "tool": "Floorplan image analyze", "command": "floorplan-analyze", "reason": "Create DXF/overlay/report."},
            ],
            AgentIntent.DWG_INSPECTION: [
                {"order": 1, "tool": "DWG object scan", "command": "scan", "reason": "Inspect DWG objects."},
                {"order": 2, "tool": "Layer counts", "command": "layers", "reason": "Inspect layers."},
                {"order": 3, "tool": "Architecture audit", "command": "analyze-architecture", "reason": "Audit drawing."},
            ],
            AgentIntent.DWG_CHANGE_REVIEW_FIRST: [
                {"order": 1, "tool": "DWG object scan", "command": "scan", "reason": "Inspect before changes."},
                {"order": 2, "tool": "JSON command dry-run", "command": "run-command --dry-run", "reason": "Preview requested changes."},
            ],
        }
        return mapping.get(intent, [{"order": 1, "tool": "Tool registry", "command": "hscad-tools", "reason": "List available tools."}])
