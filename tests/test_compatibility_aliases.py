from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from xicad_mcp.compatibility_aliases import (
    CompatibilityRegistry,
    CompatibilityWrapper,
    FileCompatibilityService,
    WrapperLoadPolicy,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "catalog/compatibility/legacy-alias-wrappers.json"
DEFAULT_LISP = ROOT / "cad/XICAD_LegacyAliases.lsp"
OVERRIDE_LISP = ROOT / "cad/XICAD_LegacyAliases_LF_Profile.lsp"


def load_registry() -> CompatibilityRegistry:
    return CompatibilityRegistry.model_validate_json(REGISTRY.read_text(encoding="utf-8"))


def test_registry_contains_all_16_reviewed_wrappers() -> None:
    registry = load_registry()
    assert registry.summary.total == 16
    assert registry.summary.default_profile == 15
    assert registry.summary.explicit_override_profile == 1
    assert registry.summary.static_validated == 16
    assert registry.summary.production_usable == 0


def test_default_profile_excludes_alias_collision() -> None:
    registry = load_registry()
    default = registry.plan()
    assert len(default) == 15
    assert "LF" not in {row.legacy_alias for row in default}
    assert all(not row.alias_collision for row in default)


def test_explicit_plan_includes_lf_collision() -> None:
    registry = load_registry()
    plan = registry.plan(include_explicit_overrides=True)
    assert len(plan) == 16
    lf = registry.find("LF")
    assert lf.legacy_symbol == "xiSelFreeze"
    assert lf.current_alias == "LLL"
    assert lf.load_policy is WrapperLoadPolicy.EXPLICIT_OVERRIDE


def test_q11_preserves_block_library_function() -> None:
    row = load_registry().find("Q11")
    assert row.current_alias == "Q1"
    assert row.legacy_symbol == row.current_symbol == "xiBlockLibrary"
    assert row.compiled_entrypoint == "C:XIBLOCKLIBRARY"


def test_every_wrapper_has_compiled_module_and_entrypoint() -> None:
    for row in load_registry().wrappers:
        assert row.module
        assert row.compiled_entrypoint.startswith("C:")
        assert row.production_usable is False


def test_default_lisp_contains_15_defs_and_not_lf() -> None:
    text = DEFAULT_LISP.read_text(encoding="utf-8")
    assert text.count("(defun C:") == 15
    assert "(defun C:1 " in text
    assert "(defun C:Q11 " in text
    assert "(defun C:LF " not in text


def test_explicit_lf_profile_is_isolated() -> None:
    text = OVERRIDE_LISP.read_text(encoding="utf-8")
    assert text.count("(defun C:") == 1
    assert "(defun C:LF (/) (xiSelFreeze) (princ))" in text
    assert "alias 2" in text


def test_file_service_returns_deterministic_plan() -> None:
    service = FileCompatibilityService(REGISTRY)
    first = service.plan()
    second = service.plan()
    assert first == second
    assert first.count == 15


def test_registry_rejects_function_substitution() -> None:
    with pytest.raises(ValidationError):
        CompatibilityWrapper(
            legacy_alias="Q11",
            legacy_symbol="xiBlockLibrary",
            current_alias="Q1",
            current_symbol="xiOtherFunction",
            compiled_entrypoint="C:XIOTHERFUNCTION",
            module="xiSym2",
            load_policy=WrapperLoadPolicy.DEFAULT,
            output_file="cad/test.lsp",
        )


def test_registry_json_has_unique_aliases() -> None:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    aliases = [row["legacy_alias"].casefold() for row in payload["wrappers"]]
    assert len(aliases) == len(set(aliases))
