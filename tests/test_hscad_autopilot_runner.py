from __future__ import annotations

from pathlib import Path

from src.orchestrator.autopilot_runner import infer_autopilot_mode, build_autopilot_steps, run_autopilot


def test_infer_contract_mode():
    assert infer_autopilot_mode("XiCAD WAL 검증 자동 진행") == "contract"


def test_build_contract_steps():
    steps = build_autopilot_steps("XiCAD 계약 검증", mode="contract", aliases="WAL,D1")
    names = [step.name for step in steps]
    assert "contract_plan" in names
    assert "review_matrix" in names
    assert "first_session" in names


def test_run_autopilot_contract_safe(tmp_path: Path):
    payload = run_autopilot("XiCAD 계약 검증", mode="contract", aliases="WAL,D1", out_dir=tmp_path, run_safe=True)
    assert payload["mode"] == "contract"
    assert payload["executed_steps"]
    assert (tmp_path / "autopilot_result.json").exists()
    assert (tmp_path / "autopilot_report.md").exists()
