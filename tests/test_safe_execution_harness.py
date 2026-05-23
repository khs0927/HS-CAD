from __future__ import annotations

from pathlib import Path

from src.execution.drawing_delta import build_delta_report, summarize_objects
from src.execution.safe_execution_package_builder import build_safe_execution_package
from src.execution.zwcad_xicad_safe_executor import SafeExecutionBlocked, ZWCADXiCADSafeExecutor
from src.workers.safe_execution_worker import run_safe_execution_dry_run_worker
from src.reports.json_exporter import export_json


COMMAND_PLAN = {
    "task": "safe execution test",
    "source_decision_package": "synthetic",
    "status": "ready_for_human_review",
    "dry_run_steps": [
        {
            "order": 1,
            "step_id": "dry-run-1",
            "title": "Prepare XiCAD layer mapping review",
            "risk": "mutation_gated",
            "command_type": "xicad-safe-plan",
            "command_hint": "xicad-safe-plan --alias LAYER-MAP",
            "source_decision_id": "action:xicad:XI-ACTION-LAYER-MAP",
            "reason": "Layer mapping requires review.",
            "preconditions": ["Original DWG must not be mutated."],
            "expected_outputs": ["dry-run action list"],
            "blocked_reason": "",
        }
    ],
    "review_table": [{"order": 1, "title": "Prepare XiCAD layer mapping review", "risk": "mutation_gated"}],
    "execution_queue_candidate": {
        "queue_id": "domain-rule-execution-candidate",
        "status": "awaiting_approval",
        "steps": [],
        "approval_required": True,
        "save_as_required": True,
        "notes": ["not execution"],
    },
    "blocked_reasons": [],
    "warnings": [],
}

REVIEW_GATE = {
    "task": "safe execution test",
    "source_command_plan": "synthetic",
    "status": "ready_for_dry_run_only",
    "checks": [],
    "signoff_required": ["Confirm original DWG will not be modified."],
    "allowed_next_steps": ["Run dry-run only"],
    "blocked_reasons": [],
    "warnings": [],
}

SIGNOFF_FALSE = {
    "status": "ready_for_dry_run_only",
    "source_command_plan": "synthetic",
    "signoff_required": ["Confirm original DWG will not be modified."],
    "allowed_next_steps": ["Run dry-run only"],
    "blocked_reasons": [],
    "operator_approved": False,
    "notes": "Review artifact only.",
}

SIGNOFF_TRUE = dict(SIGNOFF_FALSE, operator_approved=True)


def test_safe_execution_package_dry_run_is_ready():
    package = build_safe_execution_package(
        COMMAND_PLAN,
        REVIEW_GATE,
        SIGNOFF_FALSE,
        source_command_plan="plan.json",
        source_review_gate="gate.json",
        mode="dry_run",
    )

    assert package.status == "ready_for_dry_run"
    assert package.mode == "dry_run"
    assert package.operator_approved is False
    assert package.steps


def test_approved_execution_requires_operator_approval_and_copy_paths():
    package = build_safe_execution_package(
        COMMAND_PLAN,
        REVIEW_GATE,
        SIGNOFF_FALSE,
        source_command_plan="plan.json",
        source_review_gate="gate.json",
        mode="approved_copy_execution",
        original_dwg="C:/cad/original.dwg",
        working_copy_dwg="C:/cad/copy.dwg",
        save_as_target="C:/cad/output.dwg",
    )

    assert package.status == "blocked"
    assert "Operator approval is required for approved_copy_execution." in package.blocked_reasons


def test_approved_execution_blocks_same_original_and_save_as():
    package = build_safe_execution_package(
        COMMAND_PLAN,
        REVIEW_GATE,
        SIGNOFF_TRUE,
        source_command_plan="plan.json",
        source_review_gate="gate.json",
        mode="approved_copy_execution",
        original_dwg="C:/cad/original.dwg",
        working_copy_dwg="C:/cad/copy.dwg",
        save_as_target="C:/cad/original.dwg",
    )

    assert package.status == "blocked"
    assert any("save_as_target must not equal original_dwg" in reason for reason in package.blocked_reasons)


def test_executor_dry_run_does_not_require_com_adapter():
    package = build_safe_execution_package(
        COMMAND_PLAN,
        REVIEW_GATE,
        SIGNOFF_FALSE,
        source_command_plan="plan.json",
        source_review_gate="gate.json",
        mode="dry_run",
    )

    result = ZWCADXiCADSafeExecutor().dry_run(package)

    assert result["mode"] == "dry_run"
    assert result["step_count"] == 1
    assert result["steps"][0]["allowed"] is True


def test_executor_blocks_approved_execution_without_com_adapter():
    package = build_safe_execution_package(
        COMMAND_PLAN,
        REVIEW_GATE,
        SIGNOFF_TRUE,
        source_command_plan="plan.json",
        source_review_gate="gate.json",
        mode="approved_copy_execution",
        original_dwg="C:/cad/original.dwg",
        working_copy_dwg="C:/cad/copy.dwg",
        save_as_target="C:/cad/output.dwg",
    )

    assert package.status == "ready_for_approved_copy_execution"

    try:
        ZWCADXiCADSafeExecutor().execute_on_copy(package)
    except SafeExecutionBlocked as exc:
        assert "COM adapter is required" in str(exc)
    else:
        raise AssertionError("Expected SafeExecutionBlocked")


def test_drawing_delta_summarizes_counts():
    before = [{"layer": "WAL1", "entity_type": "LINE"}]
    after = [
        {"layer": "WAL1", "entity_type": "LINE"},
        {"layer": "DIM", "entity_type": "DIMENSION"},
    ]

    assert summarize_objects(before)["object_count"] == 1
    delta = build_delta_report(before, after)
    assert delta["delta"]["object_count"] == 1
    assert delta["delta"]["layer_counts"]["DIM"] == 1


def test_safe_execution_worker_writes_artifacts(tmp_path: Path):
    command_plan = tmp_path / "DOMAIN_RULE_COMMAND_PLAN.json"
    review_gate = tmp_path / "DOMAIN_RULE_REVIEW_GATE.json"
    signoff = tmp_path / "DOMAIN_RULE_SIGNOFF_MANIFEST.json"
    out_dir = tmp_path / "safe_execution"

    export_json(COMMAND_PLAN, command_plan)
    export_json(REVIEW_GATE, review_gate)
    export_json(SIGNOFF_FALSE, signoff)

    result = run_safe_execution_dry_run_worker(
        command_plan_json=command_plan,
        review_gate_json=review_gate,
        signoff_manifest_json=signoff,
        out_dir=out_dir,
    )

    assert result["status"] == "ready_for_dry_run"
    assert Path(result["package_json"]).exists()
    assert Path(result["dry_run_json"]).exists()
    assert Path(result["audit_json"]).exists()
