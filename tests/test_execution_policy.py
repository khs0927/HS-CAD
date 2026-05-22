from __future__ import annotations

from src.orchestrator.execution_policy import SafetyClass, classify_command_safety


def test_read_only_command_is_safe():
    result = classify_command_safety("scan")
    assert result.safe_to_run is True
    assert result.safety_class == SafetyClass.SAFE_READ_ONLY


def test_floorplan_analyze_is_file_output_safe():
    result = classify_command_safety("floorplan-analyze")
    assert result.safe_to_run is True
    assert result.safety_class == SafetyClass.SAFE_FILE_OUTPUT


def test_execute_is_blocked():
    result = classify_command_safety("run-command --execute")
    assert result.safe_to_run is False
    assert result.safety_class == SafetyClass.BLOCKED


def test_save_as_is_blocked():
    result = classify_command_safety("save_as")
    assert result.safe_to_run is False
    assert result.safety_class == SafetyClass.BLOCKED
