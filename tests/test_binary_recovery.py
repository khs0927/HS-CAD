from pathlib import Path

import pytest

from xicad_mcp.binary_recovery import (
    BinaryRecoveryDecision,
    FileBinaryRecoveryService,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "catalog/recovery/binary-recovery.json"


def report():
    return FileBinaryRecoveryService(REPORT).report()


def test_seven_rows_and_no_callable_claims():
    value = report()
    assert value.summary.total_aliases == 7
    assert value.summary.compiled_callable == 0
    assert value.summary.production_usable == 0
    assert all(not row.compiled_callable and not row.production_usable for row in value.commands)


def test_upgrade_registration_strings_cover_six_aliases():
    value = report()
    assert value.summary.upgrade_registration_strings == 6
    assert not value.find("SLD").upgrade_registration_string_present


def test_apd_is_deterministic_point_delete_candidate():
    row = report().find("APD")
    assert row.decision is BinaryRecoveryDecision.DETERMINISTIC_CORE_CANDIDATE
    assert row.entity_filter == "POINT"
    assert row.target_lane == "source_reimplementation"


def test_layer_filter_aliases_share_one_core():
    lfd = report().find("LFD")
    lpd = report().find("LPD")
    assert lfd.decision is BinaryRecoveryDecision.SHARED_CORE_CANDIDATE
    assert lfd.core_key == lpd.core_key == "layer_filters_delete"
    with pytest.raises(KeyError):
        report().find("xiLayerFiltersDelete")


def test_cleanup_helpers_require_review():
    for alias in ("ABD", "AGD", "LPU"):
        row = report().find(alias)
        assert row.decision is BinaryRecoveryDecision.CLEANUP_HELPER_REVIEW_REQUIRED
        assert row.helper_evidence


def test_sld_is_explicit_zwcad_platform_exclusion():
    row = report().find("SLD")
    assert row.decision is BinaryRecoveryDecision.PLATFORM_UNSUPPORTED
    assert row.unsupported_platforms == ("zwcad",)
    assert row.target_lane == "platform_exclusion"


def test_post_binary_queue_counts():
    queue = report().next_queue
    assert queue["remaining_action_commands"] == 22
    assert queue["remaining_code_commands"] == 21
    assert queue["lanes"] == {
        "consolidated_core": 4,
        "source_reimplementation": 17,
        "platform_exclusion": 1,
        "binary_recovery": 0,
    }


def test_all_shortcut_declarations_exist():
    assert all(row.backup_declaration_present for row in report().commands)
    assert all(row.current_declaration_present for row in report().commands)
