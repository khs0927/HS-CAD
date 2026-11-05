"""Run the COM adapter through real pywin32 against an in-process fake ZWCAD.

Other adapter tests replace win32com with Python fakes, so they never cross a real
IDispatch boundary. Here the fake drawing is wrapped as IDispatch by
win32com.server.util.wrap: enumeration, SAFEARRAY points, VARIANT arguments and
COM errors all go through pywin32. Nothing is registered and no CAD process is used.
"""

from __future__ import annotations

import json
import sys

import pytest
from typer.testing import CliRunner

if sys.platform != "win32":
    pytest.skip("requires Windows pywin32", allow_module_level=True)

pythoncom = pytest.importorskip("pythoncom")
win32_client = pytest.importorskip("win32com.client")
from win32com.server.exception import COMException  # noqa: E402
from win32com.server.util import ListEnumeratorGateway, NewEnum, wrap  # noqa: E402

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter  # noqa: E402
from src.app.cli import app as cli_app  # noqa: E402

COMMON = ["ObjectName", "Handle", "Layer", "Color", "Linetype", "Lineweight", "Visible"]


class _Entity:
    _public_methods_: list[str] = []
    _public_attrs_ = COMMON

    def __init__(self, object_name: str, handle: str, layer: str, **props) -> None:
        self.ObjectName = object_name
        self.Handle = handle
        self.Layer = layer
        self.Color = 256
        self.Linetype = "ByLayer"
        self.Lineweight = -1
        self.Visible = True
        for key, value in props.items():
            # A pywin32 server reads a returned tuple as (result, out-params); lists become SAFEARRAYs.
            setattr(self, key, list(value) if isinstance(value, tuple) else value)
        self._public_attrs_ = COMMON + list(props)


class _Attribute:
    _public_methods_: list[str] = []
    _public_attrs_ = ["TagString", "TextString", "InsertionPoint"]

    def __init__(self, tag: str, text: str, insert: tuple[float, float, float]) -> None:
        self.TagString = tag
        self.TextString = text
        self.InsertionPoint = list(insert)


class _Block(_Entity):
    _public_methods_ = ["GetAttributes"]

    def __init__(self, handle: str, layer: str, attributes: list[_Attribute], **props) -> None:
        super().__init__("AcDbBlockReference", handle, layer, HasAttributes=True, **props)
        self._attributes = attributes

    def GetAttributes(self):
        return [wrap(att) for att in self._attributes]


class _BrokenCircle(_Entity):
    """Reports a COM failure on one property, as a proxy entity can."""

    def __init__(self, handle: str, layer: str) -> None:
        super().__init__("AcDbCircle", handle, layer, Center=(5.0, 6.0, 0.0))
        self._public_attrs_ = self._public_attrs_ + ["Radius"]

    @property
    def Radius(self):
        raise COMException(desc="proxy entity", scode=-2147467259)


class _ModelSpace:
    _public_methods_ = ["AddLine", "AddLightWeightPolyline"]

    def __init__(self, entities: list[_Entity]) -> None:
        self.entities = entities
        self.received: list[tuple] = []

    def _NewEnum(self):
        return NewEnum(self.entities, ListEnumeratorGateway)

    def AddLine(self, start, end):
        self.received.append(("line", tuple(start), tuple(end)))
        return wrap(_Entity("AcDbLine", "F1", "0"))

    def AddLightWeightPolyline(self, coords):
        self.received.append(("polyline", tuple(coords)))
        return wrap(_Entity("AcDbPolyline", "F2", "0", Closed=False))


class _Layers:
    _public_methods_ = ["Item", "Add"]

    def Item(self, name):
        return wrap(_Entity("AcDbLayerTableRecord", "L1", name))

    def Add(self, name):
        return self.Item(name)


class _Document:
    _public_methods_ = ["Regen"]
    _public_attrs_ = ["Name", "ModelSpace", "Layers"]

    def __init__(self, model_space: _ModelSpace) -> None:
        self.Name = "fake.dwg"
        self.ModelSpace = wrap(model_space)
        self.Layers = wrap(_Layers())

    def Regen(self, _mode):
        return None


class _Documents:
    _public_methods_ = ["Open", "Add"]
    _public_attrs_ = ["Count"]

    def __init__(self, doc_dispatch) -> None:
        self.Count = 1
        self._doc = doc_dispatch
        self.opened: list[str] = []

    def Open(self, path):
        self.opened.append(path)
        return self._doc

    def Add(self):
        raise COMException(desc="scan must not create a document", scode=-2147467259)


class _Application:
    _public_methods_ = ["Update", "ZoomExtents"]
    _public_attrs_ = ["Visible", "Documents", "ActiveDocument", "Name", "Version"]

    def __init__(self, documents_dispatch, doc_dispatch) -> None:
        self.Visible = False
        self.Name = "ZWCAD"
        self.Version = "26.0"
        self.Documents = documents_dispatch
        self.ActiveDocument = doc_dispatch

    def Update(self):
        return None

    def ZoomExtents(self):
        return None


def _entities() -> list[_Entity]:
    return [
        _Entity("AcDbLine", "1A", "A-WALL", StartPoint=(0.0, 0.0, 0.0), EndPoint=(3000.0, 0.0, 0.0), Length=3000.0),
        _Entity(
            "AcDbPolyline",
            "1B",
            "A-AREA",
            Coordinates=(0.0, 0.0, 3000.0, 0.0, 3000.0, 2000.0),
            Closed=True,
            Elevation=0.0,
        ),
        _Entity(
            "AcDbText",
            "1C",
            "A-ANNO-TEXT",
            InsertionPoint=(100.0, 200.0, 0.0),
            TextString="거실",
            Height=250.0,
            Rotation=0.0,
            StyleName="Standard",
        ),
        _Block(
            "1D",
            "A-DOOR",
            [_Attribute("MARK", "D1", (1.0, 2.0, 0.0))],
            Name="DOOR",
            EffectiveName="DOOR-900",
            InsertionPoint=(500.0, 0.0, 0.0),
            Rotation=0.0,
            XScaleFactor=1.0,
            YScaleFactor=1.0,
            ZScaleFactor=1.0,
        ),
        _BrokenCircle("1E", "A-COLS"),
    ]


@pytest.fixture
def fake_zwcad(monkeypatch: pytest.MonkeyPatch):
    pythoncom.CoInitialize()
    model_space = _ModelSpace(_entities())
    doc = wrap(_Document(model_space))
    documents = _Documents(doc)
    application = win32_client.Dispatch(wrap(_Application(wrap(documents), doc)))
    progids: list[str] = []

    def _active(progid: str):
        progids.append(progid)
        return application

    real_dispatch = win32_client.Dispatch

    def _no_spawn(target, *args, **kwargs):
        # pywin32 also calls Dispatch to wrap returned IDispatch objects; only a ProgID would spawn.
        if isinstance(target, str):
            raise AssertionError(f"must attach, not spawn: {target}")
        return real_dispatch(target, *args, **kwargs)

    monkeypatch.setattr(win32_client, "GetActiveObject", _active)
    monkeypatch.setattr(win32_client, "Dispatch", _no_spawn)
    monkeypatch.delenv("ZWCAD_VERSION", raising=False)
    yield model_space, documents, progids


def test_real_pywin32_scan_keeps_rich_output(fake_zwcad):
    adapter = ZWCADCOMAdapter(visible=False)
    assert adapter.connect() is True

    rows = {row["handle"]: row for row in adapter.scan_modelspace()}

    assert adapter.active_progid == "ZWCAD.Application.2026"
    assert rows["1A"]["entity_type"] == "LINE"
    assert rows["1A"]["end"] == [3000.0, 0.0, 0.0]
    assert rows["1B"]["points"] == [[0.0, 0.0], [3000.0, 0.0], [3000.0, 2000.0]]
    assert rows["1B"]["closed"] is True
    assert rows["1C"]["text"] == "거실"
    assert rows["1C"]["insert"] == [100.0, 200.0, 0.0]
    assert rows["1D"]["effective_name"] == "DOOR-900"
    assert rows["1D"]["attributes"] == [{"tag": "MARK", "text": "D1", "insert": [1.0, 2.0, 0.0]}]
    assert rows["1E"]["center"] == [5.0, 6.0, 0.0]
    assert rows["1E"]["radius"] is None
    assert adapter.list_texts() == ["거실"]


def test_real_pywin32_variants_reach_com_as_float_arrays(fake_zwcad):
    model_space, _documents, _progids = fake_zwcad
    adapter = ZWCADCOMAdapter(visible=False)
    adapter.connect()

    adapter.create_line((1, 2), (3, 4), layer="A-WALL")
    adapter.create_polyline([(0, 0), (10, 0)], layer="A-WALL", closed=False)

    assert model_space.received == [
        ("line", (1.0, 2.0, 0.0), (3.0, 4.0, 0.0)),
        ("polyline", (0.0, 0.0, 10.0, 0.0)),
    ]


def test_cli_scan_with_real_pywin32(fake_zwcad, tmp_path):
    out = tmp_path / "objects.json"

    result = CliRunner().invoke(cli_app, ["scan", "--dwg", "active", "--out", str(out)])

    assert result.exit_code == 0, result.output
    rows = json.loads(out.read_text(encoding="utf-8"))
    assert [row["entity_type"] for row in rows] == ["LINE", "POLYLINE", "TEXT", "INSERT", "CIRCLE"]


def test_cli_analyze_architecture_with_real_pywin32(fake_zwcad, tmp_path):
    _model_space, documents, _progids = fake_zwcad
    dwg = tmp_path / "plan.dwg"
    out_dir = tmp_path / "report"

    result = CliRunner().invoke(cli_app, ["analyze-architecture", "--dwg", str(dwg), "--out-dir", str(out_dir)])

    assert result.exit_code == 0, result.output
    assert documents.opened == [str(dwg)]
    summary = json.loads((out_dir / "architecture_summary.json").read_text(encoding="utf-8"))
    assert summary["object_count"] == 5
    assert summary["block_counts"] == {"DOOR-900": 1}
    assert summary["polyline_quality"]["closed_count"] == 1
    assert "Object count: 5" in (out_dir / "drawing_audit.md").read_text(encoding="utf-8")


def test_real_pywin32_missing_progid_fails_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ZWCADCOMAdapter, "PROG_IDS", ["HSCAD.NoSuchApplication.Test"])
    adapter = ZWCADCOMAdapter(visible=False, start_if_needed=False)

    with pytest.raises(RuntimeError, match="refusing to spawn"):
        adapter.connect()

    assert adapter.app is None and adapter.active_progid is None
