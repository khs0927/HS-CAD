from __future__ import annotations

from src.orchestrator.autopilot_runner import run_autopilot


def test_autopilot_payload_has_plan_and_held(tmp_path):
    payload = run_autopilot("기존 DWG를 수정해줘", mode="dwg_review", out_dir=tmp_path, has_dwg=True, run_safe=False)
    assert "plan" in payload
    assert payload["held_steps"]
    assert payload["run_safe"] is False
