import json
from pathlib import Path

from xicad_mcp.headless_coverage import HeadlessState, build_headless_coverage

FIXTURES = Path(__file__).parent / "fixtures"
INVENTORY = FIXTURES / "xiShortkey.357.key"
WRAPPERS = FIXTURES / "legacy-alias-wrappers.json"


def report():
    data = json.loads(WRAPPERS.read_text(encoding="utf-8"))
    return build_headless_coverage(INVENTORY, {row["legacy_alias"] for row in data["wrappers"]})


def test_truthful_357_summary_after_batch9():
    summary = report().summary
    assert summary.total_commands == 357
    assert summary.headless_contract_implemented == 87
    assert summary.production_usable == 10
    assert summary.platform_excluded == 1
    assert summary.wrapper_only == 12
    assert summary.semantic_rename_only == 3
    assert summary.legacy_binary_only == 254
    assert summary.headless_contract_percent == 24.37
    assert summary.production_usable_percent == 2.8


def test_categories_sum_to_release_scope():
    summary = report().summary
    assert (
        summary.headless_contract_implemented
        + summary.platform_excluded
        + summary.wrapper_only
        + summary.semantic_rename_only
        + summary.legacy_binary_only
        == 357
    )


def test_arithmetic_is_production_usable_without_cad():
    rows = {row.alias: row for row in report().commands}
    assert rows["00"].state is HeadlessState.IMPLEMENTED
    assert rows["00"].dialog_free
    assert rows["00"].production_usable
    assert rows["00"].cad_mutation_tool_exposed is False


def test_batch5_is_headless_but_not_yet_production_live():
    rows = {row.alias: row for row in report().commands}
    for alias in ("COI", "COR", "ND", "NP", "NS", "NUC", "PY", "FAR", "TAP", "TD", "TM", "TS"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert rows[alias].production_usable is (alias in {"ND", "NP", "NS"})
        assert rows[alias].cad_mutation_tool_exposed is (
            alias in {"COI", "COR", "FAR", "NUC", "PY", "TAP", "TD", "TM", "TS"}
        )
        assert rows[alias].contract_source == "headless-core-batch5.json"


def test_verified_live_mutation_tools_are_reported_truthfully():
    rows = {row.alias: row for row in report().commands}
    for alias in (
        "ABD",
        "A2M",
        "ABE",
        "APD",
        "BAR",
        "COI",
        "COR",
        "CP",
        "CTX",
        "DAT",
        "DTD",
        "DVD",
        "FAR",
        "FAM",
        "FTT",
        "INA",
        "LIS",
        "LFD",
        "LTX",
        "LMA",
        "LNA",
        "LPP",
        "LPD",
        "LPS",
        "M2",
        "MTB1",
        "MTB2",
        "NUC",
        "NUMC",
        "PY",
        "QD",
        "RC",
        "JD",
        "SCC",
        "SCD",
        "SPN",
        "TAP",
        "T2M",
        "TC",
        "TE",
        "TFF",
        "TBM",
        "TCT",
        "TD",
        "TIC",
        "TIE",
        "TII",
        "TIN",
        "TJ",
        "TO",
        "TOA",
        "TM",
        "TS",
        "TSA",
        "TSE",
        "TSO",
        "TST",
        "TSH",
        "TSM",
        "TSW",
        "TW",
        "WAL",
    ):
        assert rows[alias].dialog_free
        assert rows[alias].cad_mutation_tool_exposed
        assert not rows[alias].production_usable


def test_wrapper_is_not_reported_as_headless():
    rows = {row.alias: row for row in report().commands}
    assert rows["Q11"].state is HeadlessState.WRAPPER_ONLY
    assert not rows["Q11"].dialog_free


def test_direct_binary_command_is_not_reported_as_headless():
    rows = {row.alias: row for row in report().commands}
    assert rows["D1"].state is HeadlessState.LEGACY_BINARY_ONLY
    assert not rows["D1"].dialog_free


def test_sld_remains_platform_excluded():
    rows = {row.alias: row for row in report().commands}
    assert rows["SLD"].state is HeadlessState.PLATFORM_EXCLUDED


def test_batch6_is_headless_but_not_yet_production_live():
    rows = {row.alias: row for row in report().commands}
    for alias in ("M2", "INA", "LIS", "LMA", "LNA", "QD", "SPN", "NUMC", "TIC", "TIE", "TII", "TIN"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (
            alias in {"INA", "LIS", "LMA", "LNA", "M2", "NUMC", "QD", "SPN", "TIC", "TIE", "TII", "TIN"}
        )
        assert rows[alias].contract_source == "headless-core-batch6.json"


def test_batch7_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    # TSP is implemented as a compatibility extension but is not one of the
    # frozen 357 aliases, so it is intentionally absent from this report.
    for alias in ("FAM", "FTT", "T2M", "TEC", "TJ", "TSA", "TSE", "TSO", "TST", "TSW", "TW"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias != "TEC")
        assert rows[alias].contract_source == "headless-core-batch7.json"


def test_batch8_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("A2M", "ABE", "CTX", "TC", "TE", "TFF", "TO", "TOA", "TSH", "TSM", "DAT", "LTX"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed
        assert rows[alias].contract_source == "headless-core-batch8.json"


def test_batch9_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("1", "2", "3", "DOL", "ELY", "EOO", "ESF", "ESO", "EW", "LAM", "LC", "LCC"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert not rows[alias].cad_mutation_tool_exposed
        assert rows[alias].contract_source == "headless-core-batch9.json"
