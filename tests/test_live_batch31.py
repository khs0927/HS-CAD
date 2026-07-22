from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch31 as live
from xicad_mcp.headless_core_batch31a import (
    AxisChangeRequest,
    AxisMode,
    AxisResetRequest,
    WorkingAxisResult,
    WorkingAxisSnapshot,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


class Doc:
    Name = "Drawing1.dwg"

    def __init__(self, angle: float = 0.5) -> None:
        self.angle = angle
        self.marks: list[str] = []
        self.set_calls: list[tuple[str, float]] = []

    def GetVariable(self, name: str) -> float:
        assert name == "SNAPANG"
        return self.angle

    def SetVariable(self, name: str, value: float) -> None:
        assert name == "SNAPANG"
        self.set_calls.append((name, value))
        self.angle = value

    def StartUndoMark(self) -> None: self.marks.append("start")
    def EndUndoMark(self) -> None: self.marks.append("end")


@pytest.fixture
def doc(monkeypatch: pytest.MonkeyPatch) -> Doc:
    drawing = Doc()
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)
    return drawing


def source(angle: float = 0.5) -> WorkingAxisSnapshot:
    return WorkingAxisSnapshot(revision="s1", snap_angle_radians=angle, state_digest=DIGEST_A)


def reset_request() -> AxisResetRequest:
    return AxisResetRequest(
        document_id="Drawing1.dwg", source=source(),
        exact_result=WorkingAxisResult(source_revision="s1", result_revision="s2", snap_angle_radians=0, state_digest=DIGEST_B),
    )


def change_request() -> AxisChangeRequest:
    return AxisChangeRequest(
        document_id="Drawing1.dwg", source=source(), mode=AxisMode.ANGLE, input_value=0.25,
        exact_result=WorkingAxisResult(source_revision="s1", result_revision="s2", snap_angle_radians=0.25, state_digest=DIGEST_B),
    )


def approved_a0(preview: dict[str, Any], request: AxisResetRequest) -> live.LiveA0ExecuteRequest:
    return live.LiveA0ExecuteRequest(
        request=request, expected_source=live.LiveAxisEvidence.model_validate(preview["expected_source"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )


def approved_a1(preview: dict[str, Any], request: AxisChangeRequest) -> live.LiveA1ExecuteRequest:
    return live.LiveA1ExecuteRequest(
        request=request, expected_source=live.LiveAxisEvidence.model_validate(preview["expected_source"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )


def test_a0_executes_only_snapang_with_undo_and_postcondition(doc: Doc) -> None:
    request = reset_request()
    preview = live.preview_live_a0(request)
    assert preview["live_executable"] and preview["mutation"]
    executed = live.execute_live_a0(approved_a0(preview, request))
    assert executed.command_alias == "A0" and executed.after_snap_angle_radians == 0
    assert doc.set_calls == [("SNAPANG", 0.0)] and doc.marks == ["start", "end"]
    assert executed.postcondition_verified


def test_a1_executes_caller_validated_exact_angle(doc: Doc) -> None:
    request = change_request()
    preview = live.preview_live_a1(request)
    executed = live.execute_live_a1(approved_a1(preview, request))
    assert executed.command_alias == "A1" and executed.after_snap_angle_radians == 0.25
    assert doc.set_calls == [("SNAPANG", 0.25)]


def test_axis_rejects_bad_fingerprint_stale_state_and_source_mismatch(doc: Doc) -> None:
    request = reset_request()
    preview = live.preview_live_a0(request)
    wrapped = approved_a0(preview, request)
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_a0(wrapped.model_copy(update={"approval_fingerprint": "sha256:" + "0" * 64}))
    doc.angle = 0.75
    with pytest.raises(ValueError, match="no longer matches"):
        live.execute_live_a0(wrapped)
    with pytest.raises(ValueError, match="source snapshot"):
        live.preview_live_a0(request)


def test_postcondition_failure_is_reported_and_undo_mark_is_closed(doc: Doc, monkeypatch: pytest.MonkeyPatch) -> None:
    request = change_request()
    preview = live.preview_live_a1(request)
    wrapped = approved_a1(preview, request)
    monkeypatch.setattr(doc, "SetVariable", lambda _name, _value: None)
    with pytest.raises(RuntimeError, match="postcondition"):
        live.execute_live_a1(wrapped)
    assert doc.marks == ["start", "end"]


def test_help_backed_complex_and_file_operations_are_preview_only() -> None:
    assert set(live.BLOCKED) == {"PUA", "SVS", "CV", "ELM", "HT", "KCI", "KCL", "PLM", "PPB", "RD", "RUB", "SAB", "SSL", "WU"}
    assert live.HELP_URLS["PUA"] == "https://izzarder.com/379"
    assert "file rollback" in live.BLOCKED["SVS"]
    assert "three-pass purge" in live.BLOCKED["SAB"]
    assert "authoritative resource" in live.BLOCKED["RUB"]


def test_registers_sixteen_previews_and_only_two_snapang_executes() -> None:
    class MCP:
        def __init__(self) -> None: self.names: list[str] = []
        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch31_tools(mcp)  # type: ignore[arg-type]
    assert len([name for name in mcp.names if "preview" in name]) == 16
    assert [name for name in mcp.names if "execute" in name] == ["xicad_execute_live_a0", "xicad_execute_live_a1"]
