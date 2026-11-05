from __future__ import annotations

from typing import Any

import pytest

from xicad_mcp import live_batch31 as live
from xicad_mcp.headless_core_batch31a import (
    AxisChangeRequest,
    AxisMode,
    AxisResetRequest,
    CopyValueRequest,
    CurrentSetting,
    EntitySnapshot,
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


class Resource:
    def __init__(self, name: str, locked: bool = False) -> None:
        self.Name, self.Lock = name, locked


class Resources:
    def __init__(self, *names: str) -> None:
        self.items = {name: Resource(name) for name in names}

    def Item(self, name: str) -> Resource:
        if name not in self.items:
            raise KeyError(name)
        return self.items[name]


class CVEntity:
    def __init__(self, object_name: str = "AcDbText") -> None:
        self.Handle, self.ObjectName = "10", object_name
        self.StyleName, self.Height, self.Layer = "ROMANS", 250.0, "A-TEXT"
        self.TextStyle = "ROMANS"
        self.Radius, self.Thickness = 125.0, 50.0
        self.PatternName, self.PatternScale = "EARTH", 25.0


class CVDoc:
    Name = "Drawing1.dwg"

    def __init__(self, entity: CVEntity | None = None) -> None:
        self.entity = entity or CVEntity()
        self.Layers = Resources("0", "A-TEXT")
        self.TextStyles = Resources("STANDARD", "ROMANS")
        self.DimStyles = Resources("STANDARD")
        self.ActiveDimStyle = self.DimStyles.Item("STANDARD")
        self.variables: dict[str, str | float] = {
            "TEXTSTYLE": "STANDARD", "TEXTSIZE": 100.0, "CLAYER": "0",
            "DIMSTYLE": "STANDARD", "FILLETRAD": 0.0, "THICKNESS": 0.0,
            "HPNAME": "ANSI31", "HPSCALE": 1.0,
        }
        self.marks: list[str] = []
        self.fail_once: str | None = None

    def HandleToObject(self, handle: str) -> CVEntity:
        if handle != self.entity.Handle:
            raise KeyError(handle)
        return self.entity

    def GetVariable(self, name: str) -> str | float:
        return self.variables[name]

    def SetVariable(self, name: str, value: str | float) -> None:
        if self.fail_once == name:
            self.fail_once = None
            raise RuntimeError("injected write failure")
        self.variables[name] = value

    def StartUndoMark(self) -> None: self.marks.append("start")
    def EndUndoMark(self) -> None: self.marks.append("end")


def cv_request(entity: CVEntity) -> CopyValueRequest:
    kind = {
        "AcDbText": "text", "AcDbHatch": "hatch", "AcDbCircle": "circle",
        "AcDbAlignedDimension": "dimension",
    }[entity.ObjectName]
    mappings = {
        "text": (("TextStyle", entity.StyleName), ("TextSize", "250"), ("Layer", entity.Layer)),
        "hatch": (("HPName", entity.PatternName), ("HPScale", "25")),
        "circle": (("FilletRad", "125"), ("Layer", entity.Layer)),
        "dimension": (("DimStyle", entity.StyleName), ("TextStyle", entity.TextStyle), ("Layer", entity.Layer)),
    }
    return CopyValueRequest(
        document_id="Drawing1.dwg",
        source=EntitySnapshot(handle=entity.Handle, revision="r1", entity_type=kind, state_digest=DIGEST_A),
        exact_settings=tuple(CurrentSetting(name=name, exact_value=str(value)) for name, value in mappings[kind]),
        result_state_digest=DIGEST_B,
    )


def approved_cv(preview: dict[str, Any], request: CopyValueRequest) -> live.LiveCVExecuteRequest:
    return live.LiveCVExecuteRequest(
        request=request,
        expected_source=live.LiveCVSourceEvidence.model_validate(preview["expected_source"]),
        approval_fingerprint=preview["approval_fingerprint"],
    )


def test_cv_copies_exact_text_settings_with_undo_and_postcondition(monkeypatch: pytest.MonkeyPatch) -> None:
    drawing = CVDoc()
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)
    request = cv_request(drawing.entity)
    preview = live.preview_live_cv(request)
    assert preview["live_executable"] and preview["mutation"]
    result = live.execute_live_cv(approved_cv(preview, request))
    assert result.changed_variables == ("TEXTSTYLE", "TEXTSIZE", "CLAYER")
    assert drawing.variables["TEXTSTYLE"] == "ROMANS"
    assert drawing.variables["TEXTSIZE"] == 250.0
    assert drawing.variables["CLAYER"] == "A-TEXT"
    assert drawing.marks == ["start", "end"] and result.postcondition_verified


def test_cv_hatch_uses_only_official_hpname_hpscale_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    drawing = CVDoc(CVEntity("AcDbHatch"))
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)
    request = cv_request(drawing.entity)
    preview = live.preview_live_cv(request)
    result = live.execute_live_cv(approved_cv(preview, request))
    assert result.changed_variables == ("HPNAME", "HPSCALE")
    assert drawing.variables["HPNAME"] == "EARTH" and drawing.variables["HPSCALE"] == 25.0
    assert drawing.variables["CLAYER"] == "0"


def test_cv_dimension_uses_writable_active_dimstyle_property(monkeypatch: pytest.MonkeyPatch) -> None:
    entity = CVEntity("AcDbAlignedDimension")
    entity.StyleName = "STANDARD"
    drawing = CVDoc(entity)
    drawing.DimStyles.items["ARCH"] = Resource("ARCH")
    entity.StyleName = "ARCH"
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)
    request = cv_request(entity)
    preview = live.preview_live_cv(request)
    result = live.execute_live_cv(approved_cv(preview, request))
    assert drawing.ActiveDimStyle.Name == "ARCH"
    assert result.changed_variables == ("DIMSTYLE", "TEXTSTYLE", "CLAYER")


def test_cv_rejects_bad_fingerprint_stale_entity_locked_or_xref_layer(monkeypatch: pytest.MonkeyPatch) -> None:
    drawing = CVDoc()
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)
    request = cv_request(drawing.entity)
    preview = live.preview_live_cv(request)
    wrapped = approved_cv(preview, request)
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_cv(wrapped.model_copy(update={"approval_fingerprint": "sha256:" + "0" * 64}))
    drawing.entity.Height = 300.0
    with pytest.raises(ValueError, match="exact values"):
        live.execute_live_cv(wrapped)
    drawing.entity.Height = 250.0
    drawing.Layers.Item("A-TEXT").Lock = True
    with pytest.raises(ValueError, match="locked or xref"):
        live.preview_live_cv(request)
    drawing.Layers.Item("A-TEXT").Lock = False
    drawing.entity.Layer = "XREF|A-TEXT"
    xref_request = cv_request(drawing.entity)
    with pytest.raises(ValueError, match="locked or xref"):
        live.preview_live_cv(xref_request)


def test_cv_rolls_back_current_settings_and_closes_undo_on_write_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    drawing = CVDoc()
    monkeypatch.setattr(live, "_drawing", lambda _name: drawing)
    request = cv_request(drawing.entity)
    preview = live.preview_live_cv(request)
    before = dict(drawing.variables)
    drawing.fail_once = "CLAYER"
    with pytest.raises(RuntimeError, match="injected"):
        live.execute_live_cv(approved_cv(preview, request))
    assert drawing.variables == before
    assert drawing.marks == ["start", "end"]


def test_help_backed_complex_and_file_operations_are_preview_only() -> None:
    assert set(live.BLOCKED) == {"PUA", "SVS", "ELM", "HT", "KCI", "KCL", "PLM", "PPB", "RD", "RUB", "SAB", "SSL", "WU"}
    assert live.HELP_URLS["PUA"] == "https://izzarder.com/379"
    assert "file rollback" in live.BLOCKED["SVS"]
    assert "three-pass purge" in live.BLOCKED["SAB"]
    assert "authoritative resource" in live.BLOCKED["RUB"]


def test_registers_sixteen_previews_and_three_atomic_executes() -> None:
    class MCP:
        def __init__(self) -> None: self.names: list[str] = []
        def tool(self, *, name: str, annotations: Any) -> Any:
            del annotations
            self.names.append(name)
            return lambda function: function

    mcp = MCP()
    live.register_live_batch31_tools(mcp)  # type: ignore[arg-type]
    assert len([name for name in mcp.names if "preview" in name]) == 16
    assert [name for name in mcp.names if "execute" in name] == [
        "xicad_execute_live_a0", "xicad_execute_live_a1", "xicad_execute_live_cv",
    ]
