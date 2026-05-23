from __future__ import annotations

from typing import Any

from src.execution.safe_execution_models import SafeExecutionPackage, SafeExecutionStep


def build_safe_execution_package(
    command_plan: dict[str, Any],
    review_gate: dict[str, Any],
    signoff_manifest: dict[str, Any],
    *,
    source_command_plan: str,
    source_review_gate: str,
    mode: str = "dry_run",
    original_dwg: str = "",
    working_copy_dwg: str = "",
    save_as_target: str = "",
) -> SafeExecutionPackage:
    task = str(command_plan.get("task") or "safe execution planning")
    blocked_reasons: list[str] = []
    warnings: list[str] = []

    gate_status = str(review_gate.get("status") or "")
    operator_approved = bool(signoff_manifest.get("operator_approved") is True)

    if gate_status == "blocked":
        blocked_reasons.append("Review gate is blocked.")

    if mode == "approved_copy_execution":
        if not operator_approved:
            blocked_reasons.append("Operator approval is required for approved_copy_execution.")
        if not working_copy_dwg:
            blocked_reasons.append("working_copy_dwg is required for approved_copy_execution.")
        if not save_as_target:
            blocked_reasons.append("save_as_target is required for approved_copy_execution.")
        if original_dwg and save_as_target and original_dwg == save_as_target:
            blocked_reasons.append("save_as_target must not equal original_dwg.")

    steps: list[SafeExecutionStep] = []
    order = 1
    for item in command_plan.get("dry_run_steps") or []:
        risk = str(item.get("risk") or "")
        if risk == "blocked":
            blocked_reasons.append(str(item.get("blocked_reason") or item.get("reason") or "Blocked command step."))
            continue

        step_mode = "dry_run"
        step_risk = "review_required"
        if mode == "approved_copy_execution" and risk == "mutation_gated":
            step_mode = "approved_copy_execution"
            step_risk = "mutation_on_copy"
        elif risk == "mutation_gated":
            step_mode = "dry_run"
            step_risk = "review_required"

        steps.append(
            SafeExecutionStep(
                order=order,
                step_id=f"safe-step-{order}",
                title=str(item.get("title") or f"Step {order}"),
                mode=step_mode,
                risk=step_risk,
                command_type=str(item.get("command_type") or "review-only"),
                command_hint=str(item.get("command_hint") or ""),
                source_plan_step_id=str(item.get("step_id") or ""),
                source_decision_id=str(item.get("source_decision_id") or ""),
                preconditions=list(item.get("preconditions") or []),
                expected_outputs=list(item.get("expected_outputs") or []),
                blocked_reason=str(item.get("blocked_reason") or ""),
                metadata={"source_step": item},
            )
        )
        order += 1

    if not steps:
        warnings.append("No executable or dry-run steps were found.")

    status = "blocked" if blocked_reasons else (
        "ready_for_approved_copy_execution" if mode == "approved_copy_execution" else "ready_for_dry_run"
    )

    return SafeExecutionPackage(
        task=task,
        source_command_plan=source_command_plan,
        source_review_gate=source_review_gate,
        mode=mode,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        save_as_required=True,
        operator_approved=operator_approved,
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
        steps=steps,
        blocked_reasons=_dedupe(blocked_reasons),
        warnings=warnings,
        required_confirmations=[
            "I confirm the original DWG will not be modified.",
            "I confirm this execution targets a copied drawing or SaveAs target.",
            "I confirm dry-run artifacts were reviewed.",
            "I confirm human approval was granted before execution.",
        ],
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out
