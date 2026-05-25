import json
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class PreflightInput:
    candidate_json: str
    allowlist_json: str
    zwcad_com_evidence_json: str
    local_validation_summary_json: str
    safety_spec_approval_md: str
    original_dwg: str
    working_copy_dwg: str
    save_as_target: str
    alias: str
    manual_live_flag: bool
    operator_approved: bool

@dataclass
class GateResult:
    id: str
    title: str
    status: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    blocked_reason: Optional[str] = None
    next_action: Optional[str] = None

@dataclass
class PreflightDecision:
    status: str
    execution_allowed: bool = False
    sendcommand_allowed: bool = False
    saveas_allowed: bool = False
    xicad_alias_execution_allowed: bool = False
    original_dwg_mutation_allowed: bool = False
    implementation_pr_can_start: bool = False
    passed_gates: List[str] = field(default_factory=list)
    blocked_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    gates: List[GateResult] = field(default_factory=list)
    evidence_summary: Dict[str, Any] = field(default_factory=dict)
    audit_intent: Dict[str, Any] = field(default_factory=dict)
    next_actions: List[str] = field(default_factory=list)
    safety: Dict[str, bool] = field(default_factory=dict)
    final_live_runner_implemented: bool = False


class FinalLiveRunnerPreflightGuard:
    def evaluate(self, p_input: PreflightInput) -> PreflightDecision:
        decision = PreflightDecision(status="blocked")
        
        # Populate safe defaults
        decision.execution_allowed = False
        decision.sendcommand_allowed = False
        decision.saveas_allowed = False
        decision.xicad_alias_execution_allowed = False
        decision.original_dwg_mutation_allowed = False
        decision.final_live_runner_implemented = False
        decision.safety = {
            "this_package_runs_cad": False,
            "this_package_calls_zwcad_com_sendcommand": False,
            "this_package_calls_saveas": False,
            "this_package_executes_xicad_alias": False,
            "this_package_mutates_original_dwg": False,
            "this_package_implements_final_live_runner": False,
            "default_execution_allowed": False
        }
        
        decision.evidence_summary = {
            "candidate_json": p_input.candidate_json,
            "allowlist_json": p_input.allowlist_json,
            "zwcad_com_evidence_json": p_input.zwcad_com_evidence_json,
            "local_validation_summary_json": p_input.local_validation_summary_json,
            "safety_spec_approval_md": p_input.safety_spec_approval_md
        }
        
        decision.audit_intent = {
            "will_open_dwg": False,
            "will_saveas": False,
            "will_sendcommand": False,
            "will_execute_xicad_alias": False,
            "will_mutate_original": False,
            "operator_approved": p_input.operator_approved,
            "manual_live_flag": p_input.manual_live_flag
        }
        
        # Evaluate Gates
        self._evaluate_gates(p_input, decision)
        
        # Determine overall status
        if decision.blocked_reasons:
            decision.status = "blocked"
        else:
            decision.status = "ready_for_manual_implementation_review"
            decision.implementation_pr_can_start = False # It is a preflight review, not implementation PR starter.
            
        return decision

    def _evaluate_gates(self, p_input: PreflightInput, decision: PreflightDecision):
        gates = []
        
        def add_gate(g: GateResult):
            gates.append(g)
            if g.status == "blocked" or g.status == "missing":
                decision.blocked_reasons.append(f"{g.id}: {g.blocked_reason}")
            elif g.status == "passed":
                decision.passed_gates.append(g.id)
            elif g.status == "warning":
                decision.warnings.append(f"{g.id}: {g.blocked_reason}")

        # 1. path-original-exists
        original_exists = Path(p_input.original_dwg).exists()
        add_gate(GateResult(
            id="gate:path-original-exists",
            title="Original DWG path exists",
            status="passed" if original_exists else "blocked",
            evidence={"exists": original_exists},
            blocked_reason="Original DWG path does not exist" if not original_exists else None
        ))
        
        # 2. path-working-copy-exists
        copy_exists = Path(p_input.working_copy_dwg).exists()
        add_gate(GateResult(
            id="gate:path-working-copy-exists",
            title="Working copy DWG path exists",
            status="passed" if copy_exists else "blocked",
            evidence={"exists": copy_exists},
            blocked_reason="Working copy DWG path does not exist" if not copy_exists else None
        ))
        
        # 3. path-save-target-distinct
        p1 = str(Path(p_input.save_as_target).resolve())
        p2 = str(Path(p_input.original_dwg).resolve())
        p3 = str(Path(p_input.working_copy_dwg).resolve())
        
        is_distinct_save = p1 != p2 and p1 != p3
        add_gate(GateResult(
            id="gate:path-save-target-distinct",
            title="Save target is distinct",
            status="passed" if is_distinct_save else "blocked",
            evidence={"is_distinct": is_distinct_save},
            blocked_reason="Save target must be distinct from original and working copy" if not is_distinct_save else None
        ))
        
        # 4. path-original-copy-distinct
        is_distinct_orig_copy = p2 != p3
        add_gate(GateResult(
            id="gate:path-original-copy-distinct",
            title="Original and copy are distinct",
            status="passed" if is_distinct_orig_copy else "blocked",
            evidence={"is_distinct": is_distinct_orig_copy},
            blocked_reason="Original and working copy must be distinct" if not is_distinct_orig_copy else None
        ))

        # 5. operator-approved
        add_gate(GateResult(
            id="gate:operator-approved",
            title="Operator Approved",
            status="passed" if p_input.operator_approved else "blocked",
            evidence={"operator_approved": p_input.operator_approved},
            blocked_reason="Operator approval is required" if not p_input.operator_approved else None
        ))
        
        # 6. manual-live-flag
        add_gate(GateResult(
            id="gate:manual-live-flag",
            title="Manual Live Flag",
            status="passed" if p_input.manual_live_flag else "blocked",
            evidence={"manual_live_flag": p_input.manual_live_flag},
            blocked_reason="Manual live flag is required" if not p_input.manual_live_flag else None
        ))
        
        # 7. allowlist-evidence-exists & 8. alias-allowlist
        allowlist_path = Path(p_input.allowlist_json)
        if allowlist_path.exists():
            try:
                with open(allowlist_path, "r", encoding="utf-8") as f:
                    allowlist = json.load(f)
                
                allowed_aliases = allowlist.get("execution_allowed_aliases", [])
                candidate_aliases = allowlist.get("candidate_aliases", [])
                
                is_alias_allowed = p_input.alias in allowed_aliases or p_input.alias in candidate_aliases
                
                add_gate(GateResult(
                    id="gate:allowlist-evidence-exists",
                    title="Allowlist evidence exists",
                    status="passed",
                    evidence={"exists": True}
                ))
                
                add_gate(GateResult(
                    id="gate:alias-allowlist",
                    title="Alias is in allowlist",
                    status="passed" if is_alias_allowed else "blocked",
                    evidence={"alias_allowed": is_alias_allowed},
                    blocked_reason="Alias is not in the allowlist" if not is_alias_allowed else None
                ))
            except Exception as e:
                add_gate(GateResult(
                    id="gate:allowlist-evidence-exists",
                    title="Allowlist evidence exists",
                    status="blocked",
                    blocked_reason=f"Invalid JSON: {e}"
                ))
                add_gate(GateResult(
                    id="gate:alias-allowlist",
                    title="Alias is in allowlist",
                    status="blocked",
                    blocked_reason="Allowlist JSON is invalid"
                ))
        else:
            add_gate(GateResult(
                id="gate:allowlist-evidence-exists",
                title="Allowlist evidence exists",
                status="missing",
                blocked_reason="Allowlist file does not exist"
            ))
            add_gate(GateResult(
                id="gate:alias-allowlist",
                title="Alias is in allowlist",
                status="missing",
                blocked_reason="Allowlist file missing"
            ))

        # 9. zwcad-com-evidence
        zwcad_path = Path(p_input.zwcad_com_evidence_json)
        if zwcad_path.exists():
            try:
                with open(zwcad_path, "r", encoding="utf-8") as f:
                    zwcad_com = json.load(f)
                
                is_valid = (
                    zwcad_com.get("status") == "confirmed" and
                    zwcad_com.get("connected") is True and
                    bool(zwcad_com.get("active_progid")) and
                    zwcad_com.get("sendcommand_used") is False and
                    zwcad_com.get("saveas_used") is False and
                    zwcad_com.get("original_dwg_mutated") is False and
                    zwcad_com.get("final_live_runner_implemented") is False
                )
                
                add_gate(GateResult(
                    id="gate:zwcad-com-evidence",
                    title="ZWCAD COM evidence is valid",
                    status="passed" if is_valid else "blocked",
                    evidence={"is_valid": is_valid},
                    blocked_reason="ZWCAD COM evidence is incomplete or invalid" if not is_valid else None
                ))
            except Exception as e:
                add_gate(GateResult(
                    id="gate:zwcad-com-evidence",
                    title="ZWCAD COM evidence is valid",
                    status="blocked",
                    blocked_reason=f"Invalid JSON: {e}"
                ))
        else:
            add_gate(GateResult(
                id="gate:zwcad-com-evidence",
                title="ZWCAD COM evidence is valid",
                status="missing",
                blocked_reason="ZWCAD COM evidence file does not exist"
            ))

        # 10. local-validation-summary
        local_val_path = Path(p_input.local_validation_summary_json)
        if local_val_path.exists():
            try:
                with open(local_val_path, "r", encoding="utf-8") as f:
                    local_val = json.load(f)
                
                is_valid = (
                    local_val.get("status") == "passed" and
                    local_val.get("all_local_validations_passed") is True and
                    local_val.get("final_live_runner_implementation_allowed") is False
                )
                
                add_gate(GateResult(
                    id="gate:local-validation-summary",
                    title="Local validation summary is valid",
                    status="passed" if is_valid else "blocked",
                    evidence={"is_valid": is_valid},
                    blocked_reason="Local validation summary is incomplete or invalid" if not is_valid else None
                ))
            except Exception as e:
                add_gate(GateResult(
                    id="gate:local-validation-summary",
                    title="Local validation summary is valid",
                    status="blocked",
                    blocked_reason=f"Invalid JSON: {e}"
                ))
        else:
            add_gate(GateResult(
                id="gate:local-validation-summary",
                title="Local validation summary is valid",
                status="missing",
                blocked_reason="Local validation summary file does not exist"
            ))

        # 11. safety-spec-design-approval
        safety_spec_path = Path(p_input.safety_spec_approval_md)
        if safety_spec_path.exists():
            try:
                with open(safety_spec_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                has_approved = "approved_for_design_only" in content
                has_false = "final_live_runner_implementation_allowed = false" in content
                has_true = "final_live_runner_implementation_allowed = true" in content
                
                is_valid = has_approved and has_false and not has_true
                
                add_gate(GateResult(
                    id="gate:safety-spec-design-approval",
                    title="Safety spec design approval",
                    status="passed" if is_valid else "blocked",
                    evidence={"is_valid": is_valid},
                    blocked_reason="Safety spec is not approved for design or allows implementation improperly" if not is_valid else None
                ))
            except Exception as e:
                add_gate(GateResult(
                    id="gate:safety-spec-design-approval",
                    title="Safety spec design approval",
                    status="blocked",
                    blocked_reason=f"Error reading file: {e}"
                ))
        else:
            add_gate(GateResult(
                id="gate:safety-spec-design-approval",
                title="Safety spec design approval",
                status="missing",
                blocked_reason="Safety spec approval markdown does not exist"
            ))
            
        # 12. phase12-candidate
        candidate_path = Path(p_input.candidate_json)
        if candidate_path.exists():
            try:
                with open(candidate_path, "r", encoding="utf-8") as f:
                    candidate = json.load(f)
                
                exec_allowed = candidate.get("execution_allowed", False)
                
                guard_path = candidate_path.parent / "PHASE12_FINAL_RUNNER_GUARD.json"
                guard_implemented = False
                if guard_path.exists():
                    with open(guard_path, "r", encoding="utf-8") as f:
                        guard = json.load(f)
                        guard_implemented = guard.get("final_runner_implemented", False)
                        
                is_valid = not exec_allowed and not guard_implemented
                
                add_gate(GateResult(
                    id="gate:phase12-candidate",
                    title="Phase 12 Candidate Guard",
                    status="passed" if is_valid else "blocked",
                    evidence={"candidate_created_or_blocked_with_reason": True, "is_valid": is_valid},
                    blocked_reason="Phase 12 candidate execution allowed or runner implemented" if not is_valid else None
                ))
            except Exception as e:
                add_gate(GateResult(
                    id="gate:phase12-candidate",
                    title="Phase 12 Candidate Guard",
                    status="blocked",
                    blocked_reason=f"Invalid JSON: {e}"
                ))
        else:
            add_gate(GateResult(
                id="gate:phase12-candidate",
                title="Phase 12 Candidate Guard",
                status="missing",
                blocked_reason="Candidate JSON does not exist"
            ))
            
        # 13. no-live-execution-in-this-pr
        add_gate(GateResult(
            id="gate:no-live-execution-in-this-pr",
            title="No live execution in this PR",
            status="passed",
            evidence={"executed": False},
            blocked_reason=None
        ))
        
        decision.gates = gates
