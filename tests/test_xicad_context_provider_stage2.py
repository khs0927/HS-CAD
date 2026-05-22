from __future__ import annotations

from src.orchestrator.xicad_context_provider import build_xicad_prompt_context, find_xicad_candidates


def test_context_provider_limits_candidates():
    context = build_xicad_prompt_context("벽체 단열 문 창", category="DRAW_ARCH", limit=3)
    command_lines = [line for line in context.splitlines() if line.startswith("- ") and " / " in line]
    assert len(command_lines) <= 3
    assert "Do not invent XiCAD commands." in context


def test_safe_search_adds_safety_fields():
    rows = find_xicad_candidates("벽체 단열 문", category="DRAW_ARCH", limit=5)
    assert rows
    assert all("risk" in row for row in rows)
    assert all("auto_run_allowed" in row for row in rows)
