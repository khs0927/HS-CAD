from __future__ import annotations

from pathlib import Path
from typing import Any

from src.execution.safe_execution_models import SafeExecutionPackage, SafeExecutionStep


ALLOWED_COMMAND_TYPES = {
    "xicad-safe-plan",
    "workflow-plan",
    "json-command-dry-run",
    "dry-run-hint",
    "review-only",
}


class SafeExecutionBlocked(RuntimeError):
    pass


class ZWCADXiCADSafeExecutor:
    def __init__(self, *, com_adapter: Any | None = None, xicad_adapter_factory: Any | None = None):
        self.com_adapter = com_adapter
        self.xicad_adapter_factory = xicad_adapter_factory

    def dry_run(self, package: SafeExecutionPackage) -> dict[str, Any]:
        return {
            "mode": "dry_run",
            "status": package.status,
            "step_count": len(package.steps),
            "steps": [self._dry_run_step(step) for step in package.steps],
            "blocked_reasons": package.blocked_reasons,
            "warnings": package.warnings,
        }

    def execute_on_copy(self, package: SafeExecutionPackage) -> dict[str, Any]:
        self._assert_can_execute(package)

        # 실제 COM 연결은 환경 의존이므로 여기서는 명확한 adapter boundary를 유지한다.
        if self.com_adapter is None:
            raise SafeExecutionBlocked("COM adapter is required for approved copy execution.")

        # 원본 대신 working_copy_dwg를 연다.
        self.com_adapter.open_document(package.working_copy_dwg)

        executed: list[dict[str, Any]] = []
        for step in package.steps:
            result = self._execute_step_on_copy(step)
            executed.append(result)

        # 반드시 SaveAs target으로 저장한다.
        self.com_adapter.save_as(package.save_as_target)

        return {
            "mode": "approved_copy_execution",
            "status": "executed_on_copy",
            "working_copy_dwg": package.working_copy_dwg,
            "save_as_target": package.save_as_target,
            "executed": executed,
        }

    def _assert_can_execute(self, package: SafeExecutionPackage) -> None:
        if package.mode != "approved_copy_execution":
            raise SafeExecutionBlocked("Package mode is not approved_copy_execution.")
        if package.status != "ready_for_approved_copy_execution":
            raise SafeExecutionBlocked(f"Package is not ready: {package.status}")
        if package.blocked_reasons:
            raise SafeExecutionBlocked("; ".join(package.blocked_reasons))
        if not package.operator_approved:
            raise SafeExecutionBlocked("operator_approved must be true.")
        if not package.working_copy_dwg:
            raise SafeExecutionBlocked("working_copy_dwg is required.")
        if not package.save_as_target:
            raise SafeExecutionBlocked("save_as_target is required.")
        if package.original_dwg and Path(package.original_dwg).resolve() == Path(package.save_as_target).resolve():
            raise SafeExecutionBlocked("save_as_target must not equal original_dwg.")

    def _dry_run_step(self, step: SafeExecutionStep) -> dict[str, Any]:
        return {
            "step_id": step.step_id,
            "title": step.title,
            "command_type": step.command_type,
            "command_hint": step.command_hint,
            "allowed": step.command_type in ALLOWED_COMMAND_TYPES,
            "risk": step.risk,
            "mode": step.mode,
            "would_execute": step.mode == "approved_copy_execution",
        }

    def _execute_step_on_copy(self, step: SafeExecutionStep) -> dict[str, Any]:
        if step.command_type not in ALLOWED_COMMAND_TYPES:
            raise SafeExecutionBlocked(f"Command type is not allowed: {step.command_type}")

        if step.command_type == "review-only":
            return {"step_id": step.step_id, "status": "skipped", "reason": "review-only step"}

        if step.command_type == "xicad-safe-plan":
            # 실제 XiCAD alias 실행은 아직 직접 실행하지 않는다.
            # 향후 xicad_adapter.safe_run(alias, args) 형태로 연결한다.
            return {
                "step_id": step.step_id,
                "status": "planned",
                "command_type": step.command_type,
                "command_hint": step.command_hint,
                "note": "XiCAD command execution remains gated; integrate alias-specific safe runner later.",
            }

        if step.command_type in {"workflow-plan", "json-command-dry-run", "dry-run-hint"}:
            return {
                "step_id": step.step_id,
                "status": "dry-run-recorded",
                "command_type": step.command_type,
                "command_hint": step.command_hint,
            }

        return {"step_id": step.step_id, "status": "ignored"}
