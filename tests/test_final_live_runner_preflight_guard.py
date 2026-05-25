import json
from pathlib import Path
from src.analysis.final_live_runner_preflight_guard import FinalLiveRunnerPreflightGuard, PreflightInput

def create_mock_files(tmp_path):
    candidate_json = tmp_path / "candidate.json"
    candidate_json.write_text(json.dumps({"execution_allowed": False}))
    
    allowlist_json = tmp_path / "allowlist.json"
    allowlist_json.write_text(json.dumps({"execution_allowed_aliases": ["WAL"], "candidate_aliases": []}))
    
    zwcad_evidence = tmp_path / "zwcad.json"
    zwcad_evidence.write_text(json.dumps({
        "status": "confirmed",
        "connected": True,
        "active_progid": "ZWCAD.Application",
        "sendcommand_used": False,
        "saveas_used": False,
        "original_dwg_mutated": False,
        "final_live_runner_implemented": False
    }))
    
    local_val = tmp_path / "local.json"
    local_val.write_text(json.dumps({
        "status": "passed",
        "all_local_validations_passed": True,
        "final_live_runner_implementation_allowed": False
    }))
    
    safety_md = tmp_path / "safety.md"
    safety_md.write_text("approved_for_design_only\nfinal_live_runner_implementation_allowed = false\n")
    
    orig_dwg = tmp_path / "original.dwg"
    orig_dwg.write_text("orig")
    
    copy_dwg = tmp_path / "copy.dwg"
    copy_dwg.write_text("copy")
    
    return {
        "candidate_json": str(candidate_json),
        "allowlist_json": str(allowlist_json),
        "zwcad_com_evidence_json": str(zwcad_evidence),
        "local_validation_summary_json": str(local_val),
        "safety_spec_approval_md": str(safety_md),
        "original_dwg": str(orig_dwg),
        "working_copy_dwg": str(copy_dwg),
        "save_as_target": str(tmp_path / "result.dwg"),
        "alias": "WAL",
        "manual_live_flag": True,
        "operator_approved": True
    }

def test_safe_defaults(tmp_path):
    guard = FinalLiveRunnerPreflightGuard()
    p_input = PreflightInput(**create_mock_files(tmp_path))
    decision = guard.evaluate(p_input)
    
    assert decision.execution_allowed is False
    assert decision.sendcommand_allowed is False
    assert decision.saveas_allowed is False
    assert decision.xicad_alias_execution_allowed is False
    assert decision.original_dwg_mutation_allowed is False
    assert decision.final_live_runner_implemented is False

def test_operator_approved_false(tmp_path):
    guard = FinalLiveRunnerPreflightGuard()
    mock = create_mock_files(tmp_path)
    mock["operator_approved"] = False
    p_input = PreflightInput(**mock)
    decision = guard.evaluate(p_input)
    
    assert decision.status == "blocked"
    assert any("operator-approved" in br for br in decision.blocked_reasons)

def test_manual_live_flag_false(tmp_path):
    guard = FinalLiveRunnerPreflightGuard()
    mock = create_mock_files(tmp_path)
    mock["manual_live_flag"] = False
    p_input = PreflightInput(**mock)
    decision = guard.evaluate(p_input)
    
    assert decision.status == "blocked"
    assert any("manual-live-flag" in br for br in decision.blocked_reasons)

def test_original_equals_copy(tmp_path):
    guard = FinalLiveRunnerPreflightGuard()
    mock = create_mock_files(tmp_path)
    mock["working_copy_dwg"] = mock["original_dwg"]
    p_input = PreflightInput(**mock)
    decision = guard.evaluate(p_input)
    
    assert decision.status == "blocked"
    assert any("original-copy-distinct" in br for br in decision.blocked_reasons)

def test_save_target_equals_original(tmp_path):
    guard = FinalLiveRunnerPreflightGuard()
    mock = create_mock_files(tmp_path)
    mock["save_as_target"] = mock["original_dwg"]
    p_input = PreflightInput(**mock)
    decision = guard.evaluate(p_input)
    
    assert decision.status == "blocked"
    assert any("save-target-distinct" in br for br in decision.blocked_reasons)

def test_zwcad_evidence_missing(tmp_path):
    guard = FinalLiveRunnerPreflightGuard()
    mock = create_mock_files(tmp_path)
    mock["zwcad_com_evidence_json"] = "does_not_exist.json"
    p_input = PreflightInput(**mock)
    decision = guard.evaluate(p_input)
    
    assert decision.status == "blocked"
    assert any("zwcad-com-evidence" in br for br in decision.blocked_reasons)

def test_zwcad_evidence_not_confirmed(tmp_path):
    guard = FinalLiveRunnerPreflightGuard()
    mock = create_mock_files(tmp_path)
    with open(mock["zwcad_com_evidence_json"], "w") as f:
        json.dump({"status": "blocked"}, f)
    
    p_input = PreflightInput(**mock)
    decision = guard.evaluate(p_input)
    
    assert decision.status == "blocked"
    assert any("zwcad-com-evidence" in br for br in decision.blocked_reasons)

def test_zwcad_evidence_sendcommand_true(tmp_path):
    guard = FinalLiveRunnerPreflightGuard()
    mock = create_mock_files(tmp_path)
    with open(mock["zwcad_com_evidence_json"], "w") as f:
        json.dump({
            "status": "confirmed",
            "connected": True,
            "active_progid": "ZWCAD.Application",
            "sendcommand_used": True, # Should block
            "saveas_used": False,
            "original_dwg_mutated": False,
            "final_live_runner_implemented": False
        }, f)
        
    p_input = PreflightInput(**mock)
    decision = guard.evaluate(p_input)
    
    assert decision.status == "blocked"
    assert any("zwcad-com-evidence" in br for br in decision.blocked_reasons)

def test_local_val_not_passed(tmp_path):
    guard = FinalLiveRunnerPreflightGuard()
    mock = create_mock_files(tmp_path)
    with open(mock["local_validation_summary_json"], "w") as f:
        json.dump({"status": "failed"}, f)
        
    p_input = PreflightInput(**mock)
    decision = guard.evaluate(p_input)
    
    assert decision.status == "blocked"
    assert any("local-validation-summary" in br for br in decision.blocked_reasons)

def test_safety_spec_no_approved_design(tmp_path):
    guard = FinalLiveRunnerPreflightGuard()
    mock = create_mock_files(tmp_path)
    with open(mock["safety_spec_approval_md"], "w") as f:
        f.write("blocked_until_zwcad_com_evidence_confirmed")
        
    p_input = PreflightInput(**mock)
    decision = guard.evaluate(p_input)
    
    assert decision.status == "blocked"
    assert any("safety-spec-design-approval" in br for br in decision.blocked_reasons)

def test_all_valid_still_no_execution(tmp_path):
    guard = FinalLiveRunnerPreflightGuard()
    mock = create_mock_files(tmp_path)
    p_input = PreflightInput(**mock)
    decision = guard.evaluate(p_input)
    
    assert decision.status == "ready_for_manual_implementation_review"
    assert decision.execution_allowed is False
    assert decision.implementation_pr_can_start is False

def test_allowlist_missing(tmp_path):
    guard = FinalLiveRunnerPreflightGuard()
    mock = create_mock_files(tmp_path)
    mock["allowlist_json"] = "does_not_exist.json"
    p_input = PreflightInput(**mock)
    decision = guard.evaluate(p_input)
    
    assert decision.status == "blocked"
    assert any("allowlist-evidence-exists" in br for br in decision.blocked_reasons)

def test_alias_not_in_allowlist(tmp_path):
    guard = FinalLiveRunnerPreflightGuard()
    mock = create_mock_files(tmp_path)
    mock["alias"] = "UNKNOWN"
    p_input = PreflightInput(**mock)
    decision = guard.evaluate(p_input)
    
    assert decision.status == "blocked"
    assert any("alias-allowlist" in br for br in decision.blocked_reasons)
