from pathlib import Path

from xicad_mcp.semantic_reconciliation import FileReconciliationService, SemanticDecision

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "catalog/compatibility/semantic-reconciliation.json"


def report():
    return FileReconciliationService(REPORT).report()


def test_four_rows():
    r = report()
    assert r.summary.total == 4
    assert r.summary.alias_preserved_rename_candidates == 3
    assert r.summary.semantic_conflicts == 1


def test_rename_candidates():
    r = report()
    for alias in ("3TP", "LII", "RR"):
        row = r.find(alias)
        assert row.decision is SemanticDecision.ALIAS_PRESERVED_RENAME_CANDIDATE
        assert row.static_alias_invocation_candidate
        assert not row.code_wrapper_required


def test_tbm_conflict():
    row = report().find("TBM")
    assert row.decision is SemanticDecision.SEMANTIC_CONFLICT
    assert row.code_wrapper_required
    assert not row.static_alias_invocation_candidate


def test_rr_description_exact():
    row = report().find("RR")
    assert row.legacy_description == row.current_description == "참조 회전"


def test_tbm_descriptions_differ():
    row = report().find("TBM")
    assert row.legacy_description != row.current_description


def test_all_have_compiled_current_entrypoints():
    assert all(row.compiled_entrypoint.startswith("C:") for row in report().commands)


def test_no_production_claims():
    assert report().summary.production_usable == 0
    assert all(not row.production_usable for row in report().commands)


def test_next_queue_counts():
    q = report().next_queue
    assert q["remaining_code_commands"] == 22
    assert q["lanes"] == {"consolidated_core": 2, "binary_recovery": 7, "source_reimplementation": 13}


def test_tbm_rerouted():
    cmds = report().next_queue["source_reimplementation_commands"]
    assert any(c["alias"] == "TBM" for c in cmds)
