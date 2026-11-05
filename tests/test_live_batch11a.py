from __future__ import annotations

import pytest

import xicad_mcp.live_batch11a as live
from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch9 import LayerEntitySnapshot, LayerSnapshot
from xicad_mcp.headless_core_batch11 import (
    DimensionKind,
    DimensionSnapshot,
    DimensionSourceDisposition,
    DimensionTextMode,
    LinearDimensionKind,
)


class FakeLayer:
    def __init__(self, name: str, *, frozen: bool = False, locked: bool = False, current: bool = False) -> None:
        self.Name, self.Color, self.Linetype = name, 7, "Continuous"
        self.LayerOn, self.Freeze, self.Lock = True, frozen, locked
        self.current = current


class FakeEntity:
    def __init__(self, handle: str, layer: str = "A") -> None:
        self.Handle, self.Layer = handle, layer
        self.Color, self.Linetype, self.Visible = 256, "ByLayer", True
        self.deleted = False

    def Delete(self) -> None:
        self.deleted = True


class FakeDimension(FakeEntity):
    def __init__(self, handle: str) -> None:
        super().__init__(handle, "DIM")
        self.StyleName, self.TextOverride = "Standard", "OLD"


class FakeModelSpace:
    def __init__(self, adapter: FakeAdapter) -> None:
        self.adapter = adapter

    def _create(self) -> FakeDimension:
        self.adapter.counter += 1
        entity = FakeDimension(f"D{self.adapter.counter}")
        self.adapter.objects[entity.Handle.casefold()] = entity
        return entity

    def AddDimAligned(self, *_args: object) -> FakeDimension:
        entity = self._create()
        entity.ObjectName = "AcDbAlignedDimension"
        return entity

    def AddDimRotated(self, *_args: object) -> FakeDimension:
        entity = self._create()
        entity.ObjectName = "AcDbRotatedDimension"
        return entity


class FakeDoc:
    Name = "Drawing1.dwg"

    def __init__(self, adapter: FakeAdapter) -> None:
        self.ModelSpace = FakeModelSpace(adapter)
        self.started = self.ended = 0

    def StartUndoMark(self) -> None:
        self.started += 1

    def EndUndoMark(self) -> None:
        self.ended += 1


class FakeAdapter:
    def __init__(self) -> None:
        self.records = {
            "0": FakeLayer("0", current=True),
            "defpoints": FakeLayer("Defpoints", frozen=True, locked=True),
            "a": FakeLayer("A", frozen=True, locked=True),
            "b": FakeLayer("B", locked=True),
            "dim": FakeLayer("DIM"),
        }
        self.objects = {"e1": FakeEntity("E1"), "d1": FakeDimension("D1")}
        self.counter = 1
        self.doc = FakeDoc(self)

    def connect(self) -> FakeDoc:
        return self.doc

    def vector(self, point: Point3D) -> tuple[float, float, float]:
        return (point.x, point.y, point.z)

    def layers(self) -> tuple[LayerSnapshot, ...]:
        return tuple(
            sorted(
                (
                    LayerSnapshot(
                        name=r.Name,
                        color_index=r.Color,
                        linetype=r.Linetype,
                        is_on=r.LayerOn,
                        is_frozen=r.Freeze,
                        is_locked=r.Lock,
                        is_current=r.current,
                    )
                    for r in self.records.values()
                ),
                key=lambda x: x.name.casefold(),
            )
        )

    def inventory(self) -> tuple[LayerEntitySnapshot, ...]:
        entity = self.objects["e1"]
        return (
            LayerEntitySnapshot(handle="E1", layer=entity.Layer, color_index=entity.Color, linetype=entity.Linetype),
        )

    def layer_objects(self) -> dict[str, FakeLayer]:
        return self.records

    def entity_objects(self) -> dict[str, FakeEntity]:
        return {handle: entity for handle, entity in self.objects.items() if not entity.deleted}

    def dimensions(
        self,
        handles: tuple[str, ...],
        dimension_line_points: dict[str, Point3D] | None = None,
    ) -> tuple[DimensionSnapshot, ...]:
        result = []
        for handle in handles:
            entity = self.objects[handle.casefold()]
            point0, point1, text = Point3D(x=0, y=0, z=0), Point3D(x=10, y=0, z=0), Point3D(x=5, y=2, z=0)
            result.append(
                DimensionSnapshot(
                    handle=entity.Handle,
                    kind=DimensionKind.ALIGNED,
                    layer=entity.Layer,
                    style=entity.StyleName,
                    measurement=10,
                    text_override=entity.TextOverride,
                    text_position=text,
                    default_text_position=text,
                    dimension_line_point=(
                        dimension_line_points[handle.casefold()] if dimension_line_points is not None else text
                    ),
                    first_extension_origin=point0,
                    second_extension_origin=point1,
                    first_extension_length=1,
                    second_extension_length=1,
                    dimscale=1,
                    ltscale=1,
                    object_scale=1,
                )
            )
        return tuple(result)


def install(monkeypatch: pytest.MonkeyPatch, adapter: FakeAdapter) -> None:
    monkeypatch.setattr(live, "ZWCADLiveBatch11aAdapter", lambda _name: adapter)


@pytest.mark.parametrize("alias", ["lt", "ltg", "luk"])
def test_all_layer_state_commands(monkeypatch: pytest.MonkeyPatch, alias: str) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    request0 = live.LiveAllLayerStatePreviewRequest(document_name="Drawing1.dwg")
    preview = getattr(live, f"preview_live_{alias}")(request0)
    request = live.LiveAllLayerStateExecuteRequest(
        **request0.model_dump(),
        expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = getattr(live, f"execute_live_{alias}")(request)
    assert result.postcondition_verified is True
    assert adapter.records["defpoints"].Freeze is True and adapter.records["defpoints"].Lock is True


def test_lu_unlocks_selected_entity_layer(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    request0 = live.LiveLuPreviewRequest(document_name="Drawing1.dwg", selected_entity_handles=("E1",))
    preview = live.preview_live_lu(request0)
    request = live.LiveLuExecuteRequest(
        **request0.model_dump(),
        expected_layers=preview["expected_layers"],
        expected_entities=preview["expected_entities"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_lu(request)
    assert result.changed_layers == ("A",) and adapter.records["a"].Lock is False


def test_cde_changes_dimension_override(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    request0 = live.LiveCdePreviewRequest(
        document_name="Drawing1.dwg", target_handles=("D1",), mode=DimensionTextMode.PREFIX_MEASUREMENT, text="L="
    )
    preview = live.preview_live_cde(request0)
    request = live.LiveCdeExecuteRequest(
        **request0.model_dump(),
        expected_layers=preview["expected_layers"],
        expected_dimensions=preview["expected_dimensions"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_cde(request)
    assert result.changed_handles == ("D1",) and adapter.objects["d1"].TextOverride == "L=< >".replace(" ", "")


def test_dcv_creates_aligned_dimension_and_preserves_source(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    request0 = live.LiveDcvPreviewRequest(
        document_name="Drawing1.dwg",
        target_handles=("D1",),
        target_kind=LinearDimensionKind.ALIGNED,
        source_disposition=DimensionSourceDisposition.PRESERVE,
        preserve_text_override=True,
        preserve_style=True,
        dimension_line_points={"D1": Point3D(x=5, y=2, z=0)},
    )
    preview = live.preview_live_dcv(request0)
    request = live.LiveDcvExecuteRequest(
        **request0.model_dump(),
        expected_layers=preview["expected_layers"],
        expected_dimensions=preview["expected_dimensions"],
        approval_fingerprint=preview["approval_fingerprint"],
    )
    result = live.execute_live_dcv(request)
    assert len(result.created_handles) == 1 and result.erased_handles == ()
    assert adapter.objects["d1"].deleted is False


def test_fingerprint_rejected_before_undo(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter()
    install(monkeypatch, adapter)
    request = live.LiveAllLayerStateExecuteRequest(
        document_name="Drawing1.dwg",
        expected_layers=adapter.layers(),
        expected_entities=adapter.inventory(),
        approval_fingerprint="sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="fingerprint"):
        live.execute_live_lt(request)
    assert adapter.doc.started == 0
