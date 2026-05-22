from __future__ import annotations

from src.orchestrator.autopilot_policy import classify_autopilot_command, AutopilotSafety


def test_safe_command_allowed():
    decision = classify_autopilot_command("xicad-contract-plan")
    assert decision.safety == AutopilotSafety.SAFE_TO_RUN
    assert decision.can_run is True


def test_execute_command_held():
    decision = classify_autopilot_command("run-command --execute")
    assert decision.safety == AutopilotSafety.HELD_FOR_REVIEW
    assert decision.can_run is False


def test_recipe_auto_modification_blocked():
    decision = classify_autopilot_command("modify recipe_registry verified=True")
    assert decision.safety == AutopilotSafety.BLOCKED
    assert decision.can_run is False
