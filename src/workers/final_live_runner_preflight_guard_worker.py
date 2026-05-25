from typing import Dict, Any
from src.analysis.final_live_runner_preflight_guard import FinalLiveRunnerPreflightGuard, PreflightInput

def run_worker(context: Dict[str, Any]) -> Dict[str, Any]:
    guard = FinalLiveRunnerPreflightGuard()
    
    p_input = PreflightInput(
        candidate_json=context.get("candidate_json", ""),
        allowlist_json=context.get("allowlist_json", ""),
        zwcad_com_evidence_json=context.get("zwcad_com_evidence_json", ""),
        local_validation_summary_json=context.get("local_validation_summary_json", ""),
        safety_spec_approval_md=context.get("safety_spec_approval_md", ""),
        original_dwg=context.get("original_dwg", ""),
        working_copy_dwg=context.get("working_copy_dwg", ""),
        save_as_target=context.get("save_as_target", ""),
        alias=context.get("alias", ""),
        manual_live_flag=context.get("manual_live_flag", False),
        operator_approved=context.get("operator_approved", False)
    )
    
    decision = guard.evaluate(p_input)
    
    # Serialize PreflightDecision to dict
    return {
        "task": "final_live_runner_preflight_guard",
        "status": decision.status,
        "execution_allowed": decision.execution_allowed,
        "sendcommand_allowed": decision.sendcommand_allowed,
        "saveas_allowed": decision.saveas_allowed,
        "xicad_alias_execution_allowed": decision.xicad_alias_execution_allowed,
        "original_dwg_mutation_allowed": decision.original_dwg_mutation_allowed,
        "final_live_runner_implemented": decision.final_live_runner_implemented,
        "implementation_pr_can_start": decision.implementation_pr_can_start,
        "passed_gates": decision.passed_gates,
        "blocked_reasons": decision.blocked_reasons,
        "warnings": decision.warnings,
        "gates": [{"id": g.id, "title": g.title, "status": g.status, "evidence": g.evidence, "blocked_reason": g.blocked_reason, "next_action": g.next_action} for g in decision.gates],
        "evidence_summary": decision.evidence_summary,
        "audit_intent": decision.audit_intent,
        "next_actions": decision.next_actions,
        "safety": decision.safety
    }
