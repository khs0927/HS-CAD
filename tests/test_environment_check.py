from __future__ import annotations

from pathlib import Path

from src.testing.environment_check import check_imports, run_environment_check, summarize_environment_check, zwcad_progid_candidates


def test_environment_check_schema_without_starting_zwcad(tmp_path: Path):
    out = tmp_path / "environment_check.json"
    payload = run_environment_check(out=out, version="2025", start_zwcad=False)
    assert out.exists()
    assert payload["zwcad_requested_version"] == "2025"
    assert "optional_imports" in payload
    assert "zwcad_progid_results" in payload
    assert "recommendations" in payload
    assert "ZWCAD 2025/2026 Environment Check" in summarize_environment_check(payload)


def test_zwcad_2025_and_2026_progids_are_supported():
    assert zwcad_progid_candidates("2025")[0] == "ZWCAD.Application.2025"
    assert zwcad_progid_candidates("2026")[0] == "ZWCAD.Application.2026"
    assert "ZWCAD.Application" in zwcad_progid_candidates()


def test_check_imports_has_expected_entries():
    names = {row["name"] for row in check_imports()}
    assert "pydantic" in names
    assert "typer" in names
