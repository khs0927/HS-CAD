import json
import logging
from pathlib import Path
import typer

from src.app.cli import app
from src.workers.final_live_runner_preflight_guard_worker import run_worker
from src.app.logger import console

logger = logging.getLogger(__name__)

@app.command("hscad-final-live-runner-preflight-guard")
def final_live_runner_preflight_guard(
    candidate_json: str = typer.Option("outputs/phase12_manual_live_candidate_verify/PHASE12_MANUAL_LIVE_EXECUTION_CANDIDATE.json", "--candidate-json"),
    allowlist_json: str = typer.Option("outputs/phase10_11_domain_copy_verify/XICAD_ALIAS_ALLOWLIST_PLAN.json", "--allowlist-json"),
    zwcad_com_evidence_json: str = typer.Option("outputs/zwcad_com_evidence_probe/ZWCAD_COM_EVIDENCE_PROBE.json", "--zwcad-com-evidence-json"),
    local_validation_summary_json: str = typer.Option("outputs/local_validation_recorder/LOCAL_VALIDATION_RESULT_SUMMARY.json", "--local-validation-summary-json"),
    safety_spec_approval_md: str = typer.Option("docs/149_final_live_runner_safety_spec_approval_after_com_probe.md", "--safety-spec-approval-md"),
    original_dwg: str = typer.Option("C:/cad/test/original.dwg", "--original-dwg"),
    working_copy_dwg: str = typer.Option("C:/cad/test_work/copy.dwg", "--working-copy-dwg"),
    save_as_target: str = typer.Option("C:/cad/test_work/result.dwg", "--save-as-target"),
    alias: str = typer.Option("WAL", "--alias"),
    manual_live_flag: bool = typer.Option(False, "--manual-live-flag/--no-manual-live-flag"),
    operator_approved: bool = typer.Option(False, "--operator-approved/--no-operator-approved"),
    out_dir: str = typer.Option("outputs/final_live_runner_preflight_guard", "--out-dir")
):
    """Run Final Live Runner Preflight Guard. Does not execute CAD."""
    logger.info("Running Final Live Runner Preflight Guard...")
    
    context = {
        "candidate_json": candidate_json,
        "allowlist_json": allowlist_json,
        "zwcad_com_evidence_json": zwcad_com_evidence_json,
        "local_validation_summary_json": local_validation_summary_json,
        "safety_spec_approval_md": safety_spec_approval_md,
        "original_dwg": original_dwg,
        "working_copy_dwg": working_copy_dwg,
        "save_as_target": save_as_target,
        "alias": alias,
        "manual_live_flag": manual_live_flag,
        "operator_approved": operator_approved
    }
    
    result = run_worker(context)
    
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    decision_json_path = out_path / "FINAL_LIVE_RUNNER_PREFLIGHT_DECISION.json"
    with open(decision_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        
    decision_md_path = out_path / "FINAL_LIVE_RUNNER_PREFLIGHT_DECISION.md"
    with open(decision_md_path, "w", encoding="utf-8") as f:
        f.write("# Final Live Runner Preflight Decision\n\n")
        f.write(f"- Status: {result.get('status')}\n")
        f.write(f"- Execution Allowed: {result.get('execution_allowed')}\n")
        f.write("\n## Blocked Reasons\n")
        for br in result.get("blocked_reasons", []):
            f.write(f"- {br}\n")
            
    audit_intent_path = out_path / "FINAL_LIVE_RUNNER_PREFLIGHT_AUDIT_INTENT.json"
    with open(audit_intent_path, "w", encoding="utf-8") as f:
        json.dump(result.get("audit_intent", {}), f, indent=2, ensure_ascii=False)
        
    refusal_reasons_path = out_path / "FINAL_LIVE_RUNNER_PREFLIGHT_REFUSAL_REASONS.json"
    with open(refusal_reasons_path, "w", encoding="utf-8") as f:
        json.dump(result.get("blocked_reasons", []), f, indent=2, ensure_ascii=False)
        
    next_plan_path = out_path / "NEXT_IMPLEMENTATION_PR_PLAN.json"
    with open(next_plan_path, "w", encoding="utf-8") as f:
        json.dump({
            "implementation_pr_can_start": result.get("implementation_pr_can_start"),
            "next_actions": result.get("next_actions", [])
        }, f, indent=2, ensure_ascii=False)
        
    if result.get("status") == "blocked":
        console.print(f"[bold red]Preflight blocked: {len(result.get('blocked_reasons', []))} reasons[/bold red]")
    else:
        console.print(f"[bold green]Preflight completed. Status: {result.get('status')}[/bold green]")
        
    logger.info(f"Generated {decision_json_path}")
