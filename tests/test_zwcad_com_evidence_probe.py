import pytest
from unittest import mock
import sys

from src.analysis.zwcad_com_evidence_probe import ZWCADCOMEvidenceProbe

def test_basic_safety_flags():
    probe = ZWCADCOMEvidenceProbe()
    # Ensure safety flags are initialized to False
    assert probe.evidence["sendcommand_used"] is False
    assert probe.evidence["saveas_used"] is False
    assert probe.evidence["original_dwg_mutated"] is False
    assert probe.evidence["xicad_alias_executed"] is False
    assert probe.evidence["final_live_runner_implemented"] is False

@mock.patch("sys.platform", "linux")
def test_non_windows_environment():
    probe = ZWCADCOMEvidenceProbe()
    result = probe.collect_evidence()
    assert result["status"] == "blocked"
    assert result["connected"] is False

def test_missing_win32com():
    with mock.patch.dict("sys.modules", {"win32com.client": None, "pythoncom": None}):
        probe = ZWCADCOMEvidenceProbe()
        result = probe.collect_evidence()
        # When win32com is absent, it should safely return insufficient or blocked
        # Our implementation sets it to "insufficient" or handles it gracefully
        assert result["status"] in ["insufficient", "blocked"]

def test_candidate_progids_not_empty():
    probe = ZWCADCOMEvidenceProbe()
    assert len(probe.CANDIDATE_PROGIDS) > 0

def test_start_if_needed_default_is_false():
    probe = ZWCADCOMEvidenceProbe()
    result = probe.collect_evidence()
    assert result["start_if_needed"] is False
    assert result["attach_only"] is True

def test_dump_evidence(tmp_path):
    probe = ZWCADCOMEvidenceProbe()
    probe.collect_evidence()
    out_file = tmp_path / "probe.json"
    probe.dump_evidence(str(out_file))
    
    assert out_file.exists()
    import json
    with open(out_file, "r") as f:
        data = json.load(f)
    assert data["evidence_type"] == "zwcad_com_probe_only"
    assert data["final_live_runner_implemented"] is False
