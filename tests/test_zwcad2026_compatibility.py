from __future__ import annotations

from src.testing.environment_check import summarize_environment_check, run_environment_check, zwcad_progid_candidates


def test_zwcad_2026_progid_is_supported():
    assert "ZWCAD.Application.2026" in zwcad_progid_candidates("2026")
    assert "ZwCAD.Application.2026" in zwcad_progid_candidates("2026")


def test_environment_summary_mentions_2025_and_2026():
    payload = run_environment_check(start_zwcad=False, version="2026")
    assert "ZWCAD 2025/2026" in summarize_environment_check(payload)
