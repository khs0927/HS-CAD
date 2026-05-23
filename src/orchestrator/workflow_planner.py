from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .tool_registry import ToolRegistry, build_default_registry


@dataclass
class WorkflowStep:
    order: int
    tool: str
    command: str
    reason: str
    status: str = "planned"
    safe_default: bool = True
    needs_review: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowPlan:
    task: str
    mode: str
    selected_intent: str
    steps: list[WorkflowStep]
    warnings: list[str] = field(default_factory=list)
    held_steps: list[str] = field(default_factory=list)
    missing_context: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "mode": self.mode,
            "selected_intent": self.selected_intent,
            "steps": [step.to_dict() for step in self.steps],
            "warnings": self.warnings,
            "held_steps": self.held_steps,
            "missing_context": self.missing_context,
        }

    def to_markdown(self) -> str:
        lines = [
            "# HS-CAD Tool Workflow Plan",
            "",
            f"- Task: {self.task}",
            f"- Mode: {self.mode}",
            f"- Selected intent: {self.selected_intent}",
            "",
            "## Ordered Steps",
            "| # | Tool | Command | Reason | Review |",
            "|---:|---|---|---|---|",
        ]
        for step in self.steps:
            review = "yes" if step.needs_review else "no"
            lines.append(f"| {step.order} | {step.tool} | `{step.command}` | {step.reason} | {review} |")
        if self.warnings:
            lines += ["", "## Warnings"] + [f"- {item}" for item in self.warnings]
        if self.held_steps:
            lines += ["", "## Steps That Need Explicit Review"] + [f"- {item}" for item in self.held_steps]
        if self.missing_context:
            lines += ["", "## Missing Context"] + [f"- {item}" for item in self.missing_context]
        return "\n".join(lines) + "\n"


def _contains(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _select(registry: ToolRegistry, names: list[str]):
    by_name = {tool.name: tool for tool in registry.all()}
    return [by_name[name] for name in names if name in by_name]


def infer_intent(task: str, *, has_image: bool = False, has_dwg: bool = False, wants_write: bool = False) -> str:
    text = task.lower()
    if has_image or _contains(text, ("image", "이미지", "pdf", "scan", "스캔", "floorplan", "평면", "도면화", "vector", "dxf")):
        if _contains(text, ("insert", "삽입", "active", "활성", "zwcad", "dwg에")):
            return "floorplan_to_active_dwg"
        return "floorplan_to_cad"
    if wants_write and has_dwg:
        return "dwg_change_review_first"
    if _contains(text, ("xicad", "벽체", "단열", "alias")):
        return "xicad_safe_workflow"
    if _contains(text, ("hssteel", "철골", "h빔", "beam", "기둥", "보")):
        return "hybrid_steel_workflow"
    if wants_write or _contains(text, ("수정", "실행", "변경", "replace", "move", "저장")):
        return "dwg_change_review_first"
    if has_dwg or _contains(text, ("dwg", "레이어", "블록", "문자", "수량", "검토", "audit")):
        return "dwg_inspection"
    return "general_safe_inspection"


def plan_hscad_workflow(
    task: str,
    *,
    has_image: bool = False,
    has_dwg: bool = False,
    wants_write: bool = False,
    registry: ToolRegistry | None = None,
) -> WorkflowPlan:
    registry = registry or build_default_registry()
    intent = infer_intent(task, has_image=has_image, has_dwg=has_dwg, wants_write=wants_write)
    warnings: list[str] = []
    held: list[str] = []
    missing: list[str] = []

    if intent == "floorplan_to_cad":
        selected = _select(registry, ["Unified environment check", "Floorplan image analyze", "neuro_seq_cad analyze"])
        if not has_image:
            missing.append("Provide --image, or use neuro_seq_cad --synthetic for a self-test.")
        warnings.append("This workflow creates DXF, overlay, and reports only.")
    elif intent == "floorplan_to_active_dwg":
        selected = _select(registry, ["Unified environment check", "Floorplan image analyze", "DWG object scan", "Architecture audit", "JSON command dry-run", "Command execution"])
        warnings.append("Use generated floorplan outputs as review artifacts before touching an active drawing.")
        held.append("Any drawing-writing step requires explicit review and SaveAs.")
    elif intent == "xicad_safe_workflow":
        selected = _select(registry, ["XiCAD profile detect", "XiCAD safe catalog", "XiCAD safe plan", "XiCAD safe run"])
        held.append("XiCAD run step should follow the safe-plan result.")
    elif intent == "hybrid_steel_workflow":
        selected = _select(registry, ["DWG object scan", "Layer counts", "Block counts", "Architecture audit", "JSON command dry-run", "Command execution"])
        warnings.append("Prefer HSSTEEL, ArchiOffice, and XiCAD rule engines before generic geometry creation.")
        held.append("Structural CAD writing requires preview and SaveAs.")
    elif intent == "dwg_change_review_first":
        selected = _select(registry, ["DWG object scan", "Layer counts", "Block counts", "Text extraction", "Architecture audit", "JSON command dry-run", "Command execution"])
        held.append("Run dry-run first, then review the generated action list.")
    elif intent == "dwg_inspection":
        selected = _select(registry, ["DWG object scan", "Layer counts", "Block counts", "Text extraction", "Architecture audit", "Quantity report"])
    else:
        selected = _select(registry, ["Unified environment check", "Tool registry", "DWG object scan", "Architecture audit"])
        missing.append("Specify whether the source is DWG, image/PDF, XiCAD command, or generated floorplan output.")

    steps: list[WorkflowStep] = []
    for index, tool in enumerate(selected, start=1):
        notes: list[str] = []
        if tool.requires_dwg and not has_dwg:
            notes.append("Needs --dwg or active drawing context.")
        if tool.requires_gpu:
            notes.append("Optional GPU/checkpoint path; fallback should be available.")
        if tool.blocked_by_default_reason:
            notes.append(tool.blocked_by_default_reason)
        steps.append(
            WorkflowStep(
                order=index,
                tool=tool.name,
                command=tool.command,
                reason=tool.purpose,
                safe_default=tool.safe_default,
                needs_review=tool.requires_execute or tool.requires_save_as,
                notes=notes,
            )
        )

    mode = "review-gated" if any(step.needs_review for step in steps) else "safe-plan"
    return WorkflowPlan(task=task, mode=mode, selected_intent=intent, steps=steps, warnings=warnings, held_steps=held, missing_context=missing)


def write_plan_files(plan: WorkflowPlan, out_dir: str | Path) -> dict[str, str]:
    import json

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "hscad_tool_workflow_plan.json"
    md_path = out / "hscad_tool_workflow_plan.md"
    json_path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(plan.to_markdown(), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}
