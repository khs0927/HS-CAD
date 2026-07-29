import json
from pathlib import Path

from xicad_mcp.headless_coverage import HeadlessState, build_headless_coverage

FIXTURES = Path(__file__).parent / "fixtures"
INVENTORY = FIXTURES / "xiShortkey.357.key"
WRAPPERS = FIXTURES / "legacy-alias-wrappers.json"


def report():
    data = json.loads(WRAPPERS.read_text(encoding="utf-8"))
    return build_headless_coverage(INVENTORY, {row["legacy_alias"] for row in data["wrappers"]})


def test_truthful_357_summary_after_batch32():
    summary = report().summary
    assert summary.total_commands == 357
    assert summary.headless_contract_implemented == 357
    assert summary.production_usable == 13
    assert summary.platform_excluded == 0
    assert summary.wrapper_only == 0
    assert summary.semantic_rename_only == 0
    assert summary.legacy_binary_only == 0
    assert summary.headless_contract_percent == 100.0
    assert summary.production_usable_percent == 3.64


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
        "1",
        "2",
        "2DP",
        "3",
        "3TP",
        "ABD",
        "A2M",
        "ABE",
        "APD",
        "BAR",
        "BE",
        "BLI",
        "BOO",
        "CBJ",
        "CB",
        "CALENDAR",
        "CEP",
        "CLI",
        "COL",
        "COI",
        "COR",
        "CP",
        "CDE",
        "DCV",
        "CTX",
        "DAT",
        "DTD",
        "DDT",
        "DE",
        "DEV",
        "DOL",
        "DPL",
        "DRL",
        "DQ",
        "DSC",
        "DSM",
        "DTM",
        "DTO",
        "DU",
        "DVD",
        "ED",
        "EED",
        "FAR",
        "FAM",
        "ELY",
        "ELV",
        "EPD",
        "EOO",
        "ESF",
        "ESO",
        "EW",
        "FTT",
        "HGRID",
        "INA",
        "IL",
        "LIS",
        "LFD",
        "LDA",
        "DLA",
        "DLL",
        "LAM",
        "LC",
        "LCC",
        "LCD",
        "LCO",
        "LCS",
        "LF",
        "LFF",
        "LFK",
        "LK",
        "LLC",
        "LOC",
        "LOS",
        "LP",
        "LTX",
        "LXP",
        "LT",
        "LTG",
        "LU",
        "LUK",
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
        "K",
        "SCC",
        "SCD",
        "SD",
        "SPN",
        "STT",
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
        "TRUSS",
        "TW",
        "WAL",
        "ZIGZAG",
        "ARD",
        "ARP",
        "ARV",
        "CNL",
        "CR",
        "CTL",
        "DAC",
        "DVC",
        "EXL",
        "MC",
        "OA",
        "OAA",
        "OB",
        "OE",
        "OI",
        "OM",
        "OO",
        "OT",
        "RM",
        "SM",
        "SS",
        "WR",
        "BMT",
        "DBC",
        "DBS",
        "TN",
        "HV",
        "HW",
        "SL",
        "QT",
        "QW",
        "TIP",
        "TOO",
        "PBB",
        "PC",
        "PEC",
        "PV",
        "PVR",
        "PVV",
        "PW",
        "R3",
        "RS",
        "V",
        "BBL",
        "BSC",
        "VL",
        "VLL",
        "VU",
        "VUU",
        "PBD",
        "A0",
        "A1",
        "JL",
        "PJ",
        "CV",
    ):
        assert rows[alias].dialog_free
        assert rows[alias].cad_mutation_tool_exposed
        assert rows[alias].production_usable is (alias == "IL")


def test_wrapper_history_now_has_an_alias_specific_headless_contract():
    rows = {row.alias: row for row in report().commands}
    assert rows["Q11"].state is HeadlessState.IMPLEMENTED
    assert rows["Q11"].dialog_free
    assert rows["Q11"].contract_source == "headless-core-batch32.json"


def test_no_direct_binary_only_command_remains_after_batch31():
    assert all(row.state is not HeadlessState.LEGACY_BINARY_ONLY for row in report().commands)


def test_sld_has_a_structured_platform_guard_contract():
    rows = {row.alias: row for row in report().commands}
    assert rows["SLD"].state is HeadlessState.IMPLEMENTED
    assert rows["SLD"].dialog_free
    assert not rows["SLD"].cad_mutation_tool_exposed
    assert rows["SLD"].contract_source == "headless-core-batch32.json"


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
        assert rows[alias].cad_mutation_tool_exposed
        assert rows[alias].contract_source == "headless-core-batch9.json"


def test_batch10_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("LCD", "LCO", "LCS", "LF", "LFF", "LFK", "LK", "LLC", "LOC", "LOS", "LP", "LST"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert rows[alias].production_usable is (alias == "LST")
        assert rows[alias].cad_mutation_tool_exposed is (alias != "LST")
        assert rows[alias].contract_source == "headless-core-batch10.json"


def test_batch11_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("LT", "LTG", "LU", "LUK", "CDE", "DCV", "DDT", "DE", "DG", "DH", "DLA", "DLL"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias not in {"DG", "DH"})
        assert rows[alias].contract_source == "headless-core-batch11.json"


def test_batch12_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("DPL", "DQ", "DSC", "DSE", "DSM", "DTM", "DTO", "DU", "ED", "IL", "LDA", "LSE"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert rows[alias].production_usable is (alias == "IL")
        assert rows[alias].cad_mutation_tool_exposed is (alias not in {"DSE", "LSE"})
        assert rows[alias].contract_source == "headless-core-batch12.json"


def test_batch13_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("LX", "SD", "TL", "2DP", "3TP", "BOO", "BS", "CBJ", "CM", "CMW", "DRL", "JUL"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (
            alias in {"SD", "2DP", "3TP", "BOO", "CBJ", "DRL"}
        )
        assert rows[alias].contract_source == "headless-core-batch13.json"


def test_batch14_frozen_inventory_members_are_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("K", "LEX", "LXP"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"K", "LXP"})
        assert rows[alias].contract_source == "headless-core-batch14.json"

    # The remaining Batch 14 planners are compatibility extensions. They are
    # not counted in the frozen xiCAD 357 inventory without legacy evidence.
    for alias in ("ME", "P2C", "PE", "PLB", "PLBC", "PLE", "PLR", "PR", "REC"):
        assert alias not in rows


def test_batch15_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("CT", "DTS", "FLT", "GEE", "STL", "COM", "EXP", "OL", "ON", "QQ", "STT", "BE"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (
            alias in {"CT", "DTS", "FLT", "GEE", "STT", "BE"}
        )
        assert rows[alias].contract_source == "headless-core-batch15.json"


def test_batch16_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("BLI", "BPT", "CALENDAR", "CEP", "CLI", "COL", "CW", "D1", "D2", "D3", "DEV", "EED"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert rows[alias].production_usable is (alias == "BPT")
        assert rows[alias].cad_mutation_tool_exposed is (
            alias in {"BLI", "CALENDAR", "CEP", "CLI", "COL", "DEV", "EED"}
        )
        assert rows[alias].contract_source == "headless-core-batch16.json"


def test_batch17_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("ELV", "EPD", "HB", "HGRID", "HP", "INS", "PK", "PZ", "QRC", "SCB", "STB", "STC"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"ELV", "EPD", "HGRID"})
        assert rows[alias].contract_source == "headless-core-batch17.json"


def test_batch18_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("STP", "TAJ", "TRUSS", "W1", "W2", "W3", "WO", "ZIGZAG", "C2E", "E2C", "HC", "HEX"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"TAJ", "TRUSS", "ZIGZAG"})
        assert rows[alias].contract_source == "headless-core-batch18.json"


def test_batch19a_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("HM", "HPM", "RDS", "SOL", "TB", "TBT"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"SOL", "TB", "TBT"})
        assert rows[alias].contract_source == "headless-core-batch19a.json"


def test_batch19b_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("BAT", "BB", "BRO", "CB", "CUT", "DTP"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"BAT", "BB", "BRO", "CB"})
        assert rows[alias].contract_source == "headless-core-batch19b.json"


def test_batch20a_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("FE", "FM", "FR", "FT", "FX", "XT"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert not rows[alias].cad_mutation_tool_exposed
        assert rows[alias].contract_source == "headless-core-batch20a.json"


def test_batch20b_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("ARD", "ARP", "ARV", "CNL", "CR", "CTL"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed
        assert rows[alias].contract_source == "headless-core-batch20b.json"


def test_batch21a_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("DAC", "DVC", "EXL", "JL", "MC", "MLC"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"DAC", "DVC", "EXL", "JL", "MC"})
        assert rows[alias].contract_source == "headless-core-batch21a.json"


def test_batch21b_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("MM", "OA", "OAA", "OB", "OE", "OI"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"OA", "OAA", "OB", "OE", "OI"})
        assert rows[alias].contract_source == "headless-core-batch21b.json"


def test_batch22a_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("OM", "OO", "OT", "RDC", "RM", "SB"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"OM", "OO", "OT", "RM"})
        assert rows[alias].contract_source == "headless-core-batch22a.json"


def test_batch22b_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("SM", "SS", "WR", "BMT", "DAS", "DBC"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"SM", "SS", "WR", "BMT", "DBC"})
        assert rows[alias].contract_source == "headless-core-batch22b.json"


def test_batch23a_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("DBS", "DFS", "DSB", "MDL", "PBS", "TN"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"DBS", "TN"})
        assert rows[alias].contract_source == "headless-core-batch23a.json"


def test_batch23b_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("TOB", "ZR", "AE", "AHM", "BA", "CDB"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert not rows[alias].cad_mutation_tool_exposed
        assert rows[alias].contract_source == "headless-core-batch23b.json"


def test_batch24a_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("CDN", "DAR", "DEE", "DM", "FFO", "HV"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias == "HV")
        assert rows[alias].contract_source == "headless-core-batch24a.json"


def test_batch24b_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("HW", "MAC", "MRT", "SAR", "SCA", "SE"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias == "HW")
        assert rows[alias].contract_source == "headless-core-batch24b.json"


def test_batch25a_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("SL", "ZAE", "QT", "QW", "TIP", "TOO"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"SL", "QT", "QW", "TIP", "TOO"})
        assert rows[alias].contract_source == "headless-core-batch25a.json"


def test_batch25b_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("TTT", "TX", "MTLT", "PBB", "PC", "PEC"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"TX", "PBB", "PC", "PEC"})
        assert rows[alias].contract_source == "headless-core-batch25b.json"


def test_batch26a_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("PJ", "PV", "PVL", "PVR", "PVV", "PW"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"PJ", "PV", "PVR", "PVV", "PW"})
        assert rows[alias].contract_source == "headless-core-batch26a.json"


def test_batch26b_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("PWD", "R3", "RND", "RS", "UFD", "V"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"R3", "RS", "V"})
        assert rows[alias].contract_source == "headless-core-batch26b.json"


def test_batch27a_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("XZ", "ABX", "B2X", "BAD", "BAM", "BBL"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias == "BBL")
        assert rows[alias].contract_source == "headless-core-batch27a.json"


def test_batch27b_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("BCC", "BCH", "BCO", "BEX", "BIN", "BLA"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert not rows[alias].cad_mutation_tool_exposed
        assert rows[alias].contract_source == "headless-core-batch27b.json"


def test_batch28a_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("BLX", "BQT", "BRM", "BRN", "BSC", "CX"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"BRN", "BSC"})
        assert rows[alias].contract_source == "headless-core-batch28a.json"


def test_batch28b_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("EAR", "M2B", "MFB", "MFX", "MX", "QWB"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert not rows[alias].cad_mutation_tool_exposed
        assert rows[alias].contract_source == "headless-core-batch28b.json"


def test_batch29a_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("RBP", "WSL", "XCX", "XRC", "XRR", "P2M"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert not rows[alias].cad_mutation_tool_exposed
        assert rows[alias].contract_source == "headless-core-batch29a.json"


def test_batch29b_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("VA", "VGL", "VL", "VLL", "VMO", "VPP"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"VL", "VLL"})
        assert rows[alias].contract_source == "headless-core-batch29b.json"


def test_batch30a_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("VR", "VSD", "VU", "VUU", "BAK", "CER"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"VU", "VUU"})
        assert rows[alias].contract_source == "headless-core-batch30a.json"


def test_batch30b_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("IB", "MSL", "PB", "PBD", "PBM", "PPP"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias == "PBD")
        assert rows[alias].contract_source == "headless-core-batch30b.json"


def test_batch31a_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("PUA", "SVS", "A0", "A1", "CV", "ELM", "HT", "KCI"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias in {"A0", "A1", "CV"})
        assert rows[alias].contract_source == "headless-core-batch31a.json"


def test_batch31b_is_headless_and_dialog_free():
    rows = {row.alias: row for row in report().commands}
    for alias in ("KCL", "PLM", "PPB", "RD", "RUB", "SAB", "SSL", "WU"):
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert not rows[alias].cad_mutation_tool_exposed
        assert rows[alias].contract_source == "headless-core-batch31b.json"


def test_batch32_closes_wrapper_rename_and_platform_contracts():
    rows = {row.alias: row for row in report().commands}
    aliases = ("CE", "BBB", "FF", "WQ", "WE", "XX", "Q11", "MK", "RR", "LII", "SLD")
    for alias in aliases:
        assert rows[alias].state is HeadlessState.IMPLEMENTED
        assert rows[alias].dialog_free
        assert not rows[alias].production_usable
        assert rows[alias].cad_mutation_tool_exposed is (alias == "RR")
        assert rows[alias].contract_source == "headless-core-batch32.json"
