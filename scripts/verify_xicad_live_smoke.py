"""Safe, reversible ZWCAD 2026 smoke tests for representative xiCAD live adapters.

The harness deliberately targets exactly one open ``Drawing1.dwg``.  Each
scenario creates its own uniquely named layer and temporary fixture objects,
executes one approved live adapter request, verifies the resulting CAD state,
and uses ZWCAD Undo to restore the drawing to its pre-scenario state.

It never saves the drawing.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections.abc import Callable, Iterable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from xicad_mcp.headless_core_batch1 import Point3D
from xicad_mcp.headless_core_batch15 import ContentKind, CopyContentsRequest, DateStampRequest, FlattenRequest
from xicad_mcp.headless_core_batch19a import (
    SolidHatchRequest,
    TableKind,
    TableMethod,
    TableRequest,
    TableTextCell,
    TableTextRequest,
)
from xicad_mcp.headless_core_batch32 import (
    EntitySnapshot,
    ExactChangeSet,
    ExactEntityResult,
    ReferenceRotateRequest,
)
from xicad_mcp.headless_core_batch32 import (
    Point3D as RRPoint3D,
)
from xicad_mcp.live_batch15a import (
    LiveContentEvidence,
    LiveCtExecuteRequest,
    LiveDtsExecuteRequest,
    LiveFltExecuteRequest,
    LiveGeometryEvidence,
    LiveLayerEvidence,
    execute_live_ct,
    execute_live_dts,
    execute_live_flt,
    preview_live_ct,
    preview_live_dts,
    preview_live_flt,
)
from xicad_mcp.live_batch19 import (
    LiveBoundaryEvidence,
    LiveSolExecuteRequest,
    LiveTableEvidence,
    LiveTbExecuteRequest,
    LiveTbtExecuteRequest,
    execute_live_sol,
    execute_live_tb,
    execute_live_tbt,
    preview_live_sol,
    preview_live_tb,
    preview_live_tbt,
)
from xicad_mcp.live_batch19 import (
    LiveLayerEvidence as LiveBatch19LayerEvidence,
)
from xicad_mcp.live_batch32 import (
    LiveRREntityEvidence,
    LiveRRExecuteRequest,
    execute_live_rr,
    preview_live_rr,
)

DOCUMENT_NAME = "Drawing1.dwg"
PROG_ID = "ZWCAD.Application.2026"
SCENARIOS = ("ct", "dts", "flt", "sol", "tb", "tbt", "rr")


class SmokeVerificationError(RuntimeError):
    """Raised when a live-CAD smoke precondition or postcondition fails."""


def _point(x: float, y: float, z: float = 0.0) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [x, y, z])


def _double_array(values: Iterable[float]) -> Any:
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        [float(value) for value in values],
    )


def _exact_document(app: Any, name: str = DOCUMENT_NAME) -> Any:
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == name.casefold()]
    if len(matches) != 1:
        raise SmokeVerificationError(f"expected exactly one open {name}, found {len(matches)}")
    if str(matches[0].Name) != name:
        raise SmokeVerificationError(f"document name must be exactly {name!r}, got {matches[0].Name!r}")
    return matches[0]


def _model_handles(doc: Any) -> set[str]:
    return {str(entity.Handle).casefold() for entity in doc.ModelSpace}


def _layer_exists(doc: Any, name: str) -> bool:
    try:
        doc.Layers.Item(name)
    except Exception:
        return False
    return True


def _is_idle(doc: Any) -> bool:
    return int(doc.GetVariable("CMDACTIVE")) == 0


def _wait_for(
    predicate: Callable[[], bool],
    *,
    timeout: float,
    interval: float = 0.1,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    deadline = clock() + timeout
    while True:
        if predicate():
            return
        if clock() >= deadline:
            raise SmokeVerificationError("timed out while waiting for ZWCAD postcondition")
        sleeper(interval)


def _undo_and_wait(doc: Any, predicate: Callable[[], bool], *, timeout: float) -> None:
    if not _is_idle(doc):
        raise SmokeVerificationError("CMDACTIVE must be 0 before Undo")
    doc.SendCommand("_.UNDO\n1\n")
    _wait_for(lambda: _is_idle(doc) and predicate(), timeout=timeout)


def _entity_by_handle(doc: Any, handle: str) -> Any | None:
    try:
        return doc.HandleToObject(handle)
    except Exception:
        return None


def _coords(value: Any) -> tuple[float, float, float]:
    xyz = tuple(float(item) for item in value)
    return xyz[0], xyz[1], xyz[2]


def _close(a: float, b: float, tolerance: float = 1e-8) -> bool:
    return abs(a - b) <= tolerance


def _same_point(left: Any, right: tuple[float, float, float]) -> bool:
    return all(_close(actual, expected) for actual, expected in zip(_coords(left), right, strict=True))


def _scenario_origin(doc: Any, ordinal: int) -> tuple[float, float]:
    try:
        maximum = tuple(float(value) for value in doc.GetVariable("EXTMAX"))
        x_max, y_max = maximum[0], maximum[1]
        if not all(math.isfinite(value) and abs(value) < 1.0e12 for value in (x_max, y_max)):
            x_max = y_max = 0.0
    except Exception:
        x_max = y_max = 0.0
    offset = 10_000.0 + ordinal * 2_000.0
    return x_max + offset, y_max + offset


def _new_layer_name(alias: str) -> str:
    return f"HSCAD_XICAD_SMOKE_{alias.upper()}_{uuid4().hex[:10].upper()}"


def _setup_layer(doc: Any, name: str) -> Any:
    if _layer_exists(doc, name):
        raise SmokeVerificationError(f"temporary layer unexpectedly exists: {name}")
    layer = doc.Layers.Add(name)
    layer.Color = 8
    return layer


def _begin_setup(doc: Any) -> None:
    if not _is_idle(doc):
        raise SmokeVerificationError(f"CMDACTIVE must be 0, got {doc.GetVariable('CMDACTIVE')}")
    doc.StartUndoMark()


def _end_setup(doc: Any) -> None:
    doc.EndUndoMark()


def _cleanup_direct(doc: Any, layer_name: str) -> None:
    """Best-effort failure cleanup limited strictly to the unique smoke layer."""
    entities = [
        entity for entity in doc.ModelSpace if str(getattr(entity, "Layer", "")).casefold() == layer_name.casefold()
    ]
    for entity in reversed(entities):
        try:
            entity.Delete()
        except Exception:
            pass
    try:
        doc.Layers.Item(layer_name).Delete()
    except Exception:
        pass
    try:
        doc.Regen(1)
    except Exception:
        pass


def _result(alias: str, layer: str, before: set[str], after: set[str], **details: Any) -> dict[str, Any]:
    return {
        "alias": alias,
        "status": "passed",
        "temporary_layer": layer,
        "object_count_before": len(before),
        "object_count_after_restore": len(after),
        "handles_restored": before == after,
        "undo_restored": before == after,
        "postcondition_verified": True,
        **details,
    }


def _run_ct(doc: Any, *, timeout: float, origin: tuple[float, float]) -> dict[str, Any]:
    alias, layer_name = "CT", _new_layer_name("CT")
    baseline = _model_handles(doc)
    source = target = None
    try:
        _begin_setup(doc)
        try:
            _setup_layer(doc, layer_name)
            source = doc.ModelSpace.AddText("HSCAD-SMOKE-SOURCE", _point(origin[0], origin[1]), 250.0)
            target = doc.ModelSpace.AddText("HSCAD-SMOKE-TARGET", _point(origin[0], origin[1] - 500.0), 250.0)
            source.Layer = target.Layer = layer_name
        finally:
            _end_setup(doc)

        source_handle, target_handle = str(source.Handle), str(target.Handle)
        request = CopyContentsRequest(
            document_id=DOCUMENT_NAME,
            source_handle=source_handle,
            target_handles=(target_handle,),
            expected_kind=ContentKind.TEXT,
        )
        preview = preview_live_ct(request)
        execution = LiveCtExecuteRequest(
            request=request,
            expected_contents=tuple(LiveContentEvidence.model_validate(item) for item in preview["expected_contents"]),
            approval_fingerprint=preview["approval_fingerprint"],
        )
        adapter_result = execute_live_ct(execution)
        current_target = _entity_by_handle(doc, target_handle)
        if current_target is None or str(current_target.TextString) != "HSCAD-SMOKE-SOURCE":
            raise SmokeVerificationError("CT did not copy the exact source text")

        _undo_and_wait(
            doc,
            lambda: (
                (entity := _entity_by_handle(doc, target_handle)) is not None
                and str(entity.TextString) == "HSCAD-SMOKE-TARGET"
            ),
            timeout=timeout,
        )
        _undo_and_wait(
            doc,
            lambda: _model_handles(doc) == baseline and not _layer_exists(doc, layer_name),
            timeout=timeout,
        )
        restored = _model_handles(doc)
        return _result(
            alias,
            layer_name,
            baseline,
            restored,
            adapter_result=adapter_result.model_dump(mode="json"),
            verified_attributes={"target_text": "HSCAD-SMOKE-SOURCE"},
        )
    except Exception:
        _cleanup_direct(doc, layer_name)
        raise


def _run_dts(doc: Any, *, timeout: float, origin: tuple[float, float]) -> dict[str, Any]:
    alias, layer_name = "DTS", _new_layer_name("DTS")
    baseline = _model_handles(doc)
    try:
        _begin_setup(doc)
        try:
            _setup_layer(doc, layer_name)
        finally:
            _end_setup(doc)

        style_name = str(doc.GetVariable("TEXTSTYLE"))
        stamp_date = date(2026, 7, 29)
        request = DateStampRequest(
            document_id=DOCUMENT_NAME,
            creation_date=stamp_date,
            insertion_point=Point3D(x=origin[0], y=origin[1]),
            format_template="%Y-%m-%d",
            prefix="HSCAD-SMOKE-",
            layer=layer_name,
            text_style=style_name,
            text_height=250.0,
        )
        preview = preview_live_dts(request)
        execution = LiveDtsExecuteRequest(
            request=request,
            expected_layer=LiveLayerEvidence.model_validate(preview["expected_layer"]),
            approval_fingerprint=preview["approval_fingerprint"],
        )
        adapter_result = execute_live_dts(execution)
        if len(adapter_result.created_handles) != 1:
            raise SmokeVerificationError("DTS must create exactly one text entity")
        created_handle = adapter_result.created_handles[0]
        entity = _entity_by_handle(doc, created_handle)
        expected_text = "HSCAD-SMOKE-2026-07-29"
        if (
            entity is None
            or str(entity.ObjectName).casefold() != "acdbtext"
            or str(entity.TextString) != expected_text
            or str(entity.Layer).casefold() != layer_name.casefold()
            or not _close(float(entity.Height), 250.0)
        ):
            raise SmokeVerificationError("DTS created-text postcondition failed")

        _undo_and_wait(doc, lambda: _entity_by_handle(doc, created_handle) is None, timeout=timeout)
        _undo_and_wait(
            doc,
            lambda: _model_handles(doc) == baseline and not _layer_exists(doc, layer_name),
            timeout=timeout,
        )
        restored = _model_handles(doc)
        return _result(
            alias,
            layer_name,
            baseline,
            restored,
            adapter_result=adapter_result.model_dump(mode="json"),
            verified_attributes={
                "object_name": "AcDbText",
                "text": expected_text,
                "height": 250.0,
                "layer": layer_name,
            },
        )
    except Exception:
        _cleanup_direct(doc, layer_name)
        raise


def _run_flt(doc: Any, *, timeout: float, origin: tuple[float, float]) -> dict[str, Any]:
    alias, layer_name = "FLT", _new_layer_name("FLT")
    baseline = _model_handles(doc)
    line = None
    original_start = (origin[0], origin[1], 125.0)
    original_end = (origin[0] + 1000.0, origin[1] + 500.0, -75.0)
    try:
        _begin_setup(doc)
        try:
            _setup_layer(doc, layer_name)
            line = doc.ModelSpace.AddLine(_point(*original_start), _point(*original_end))
            line.Layer = layer_name
        finally:
            _end_setup(doc)

        handle = str(line.Handle)
        request = FlattenRequest(document_id=DOCUMENT_NAME, target_handles=(handle,), target_z=0.0)
        preview = preview_live_flt(request)
        execution = LiveFltExecuteRequest(
            request=request,
            expected_geometry=tuple(LiveGeometryEvidence.model_validate(item) for item in preview["expected_geometry"]),
            approval_fingerprint=preview["approval_fingerprint"],
        )
        adapter_result = execute_live_flt(execution)
        current = _entity_by_handle(doc, handle)
        if (
            current is None
            or not _close(_coords(current.StartPoint)[2], 0.0)
            or not _close(_coords(current.EndPoint)[2], 0.0)
        ):
            raise SmokeVerificationError("FLT did not flatten both line endpoints to Z=0")

        _undo_and_wait(
            doc,
            lambda: (
                (entity := _entity_by_handle(doc, handle)) is not None
                and _same_point(entity.StartPoint, original_start)
                and _same_point(entity.EndPoint, original_end)
            ),
            timeout=timeout,
        )
        _undo_and_wait(
            doc,
            lambda: _model_handles(doc) == baseline and not _layer_exists(doc, layer_name),
            timeout=timeout,
        )
        restored = _model_handles(doc)
        return _result(
            alias,
            layer_name,
            baseline,
            restored,
            adapter_result=adapter_result.model_dump(mode="json"),
            verified_attributes={"start_z": 0.0, "end_z": 0.0},
        )
    except Exception:
        _cleanup_direct(doc, layer_name)
        raise


def _run_sol(doc: Any, *, timeout: float, origin: tuple[float, float]) -> dict[str, Any]:
    alias, layer_name = "SOL", _new_layer_name("SOL")
    baseline = _model_handles(doc)
    circle = polyline = None
    try:
        _begin_setup(doc)
        try:
            _setup_layer(doc, layer_name)
            circle = doc.ModelSpace.AddCircle(_point(origin[0], origin[1]), 500.0)
            polyline = doc.ModelSpace.AddLightWeightPolyline(
                _double_array(
                    (
                        origin[0] + 1500.0,
                        origin[1] - 500.0,
                        origin[0] + 2500.0,
                        origin[1] - 500.0,
                        origin[0] + 2500.0,
                        origin[1] + 500.0,
                        origin[0] + 1500.0,
                        origin[1] + 500.0,
                    )
                )
            )
            polyline.Closed = True
            circle.Layer = polyline.Layer = layer_name
        finally:
            _end_setup(doc)

        boundary_handles = (str(circle.Handle), str(polyline.Handle))
        request = SolidHatchRequest(
            document_id=DOCUMENT_NAME,
            boundary_handles=boundary_handles,
            layer=layer_name,
            color=3,
            associative=True,
            island_detection="normal",
        )
        preview = preview_live_sol(request)
        execution = LiveSolExecuteRequest(
            request=request,
            expected_boundaries=tuple(
                LiveBoundaryEvidence.model_validate(item) for item in preview["expected_boundaries"]
            ),
            expected_target_layer=LiveBatch19LayerEvidence.model_validate(preview["expected_target_layer"]),
            approval_fingerprint=preview["approval_fingerprint"],
        )
        adapter_result = execute_live_sol(execution)
        if len(adapter_result.created_handles) != 2:
            raise SmokeVerificationError("SOL must create one hatch for each circle/polyline boundary")
        hatches = [_entity_by_handle(doc, handle) for handle in adapter_result.created_handles]
        if any(
            hatch is None
            or str(hatch.ObjectName).casefold() != "acdbhatch"
            or str(hatch.PatternName).casefold() != "solid"
            or str(hatch.Layer).casefold() != layer_name.casefold()
            or int(hatch.Color) != 3
            for hatch in hatches
        ):
            raise SmokeVerificationError("SOL hatch property postcondition failed")

        _undo_and_wait(
            doc,
            lambda: (
                all(_entity_by_handle(doc, handle) is None for handle in adapter_result.created_handles)
                and all(_entity_by_handle(doc, handle) is not None for handle in boundary_handles)
            ),
            timeout=timeout,
        )
        _undo_and_wait(
            doc,
            lambda: _model_handles(doc) == baseline and not _layer_exists(doc, layer_name),
            timeout=timeout,
        )
        return _result(
            alias,
            layer_name,
            baseline,
            _model_handles(doc),
            adapter_result=adapter_result.model_dump(mode="json"),
            fixture_boundary_types=("AcDbCircle", "AcDbPolyline"),
            verified_attributes={"hatch_count": 2, "pattern": "SOLID", "color": 3, "associative": True},
        )
    except Exception:
        _cleanup_direct(doc, layer_name)
        raise


def _run_tb(doc: Any, *, timeout: float, origin: tuple[float, float]) -> dict[str, Any]:
    alias, layer_name = "TB", _new_layer_name("TB")
    baseline = _model_handles(doc)
    try:
        _begin_setup(doc)
        try:
            _setup_layer(doc, layer_name)
        finally:
            _end_setup(doc)

        request = TableRequest(
            document_id=DOCUMENT_NAME,
            insertion_point=Point3D(x=origin[0], y=origin[1]),
            kind=TableKind.GENERAL,
            method=TableMethod.EXPLICIT_SPACING,
            row_count=2,
            column_count=2,
            row_heights=(600.0, 800.0),
            column_widths=(1000.0, 1200.0),
            approximate_division=False,
            layer=layer_name,
        )
        preview = preview_live_tb(request)
        execution = LiveTbExecuteRequest(
            request=request,
            expected_target_layer=LiveBatch19LayerEvidence.model_validate(preview["expected_target_layer"]),
            approval_fingerprint=preview["approval_fingerprint"],
        )
        adapter_result = execute_live_tb(execution)
        if len(adapter_result.created_handles) != 6:
            raise SmokeVerificationError("TB 2x2 grid must create exactly six lines")
        lines = [_entity_by_handle(doc, handle) for handle in adapter_result.created_handles]
        if any(
            line is None
            or str(line.ObjectName).casefold() != "acdbline"
            or str(line.Layer).casefold() != layer_name.casefold()
            for line in lines
        ):
            raise SmokeVerificationError("TB line-grid property postcondition failed")
        xs = [coordinate for line in lines for coordinate in (_coords(line.StartPoint)[0], _coords(line.EndPoint)[0])]
        ys = [coordinate for line in lines for coordinate in (_coords(line.StartPoint)[1], _coords(line.EndPoint)[1])]
        if not (
            _close(min(xs), origin[0])
            and _close(max(xs), origin[0] + 2200.0)
            and _close(min(ys), origin[1] - 1400.0)
            and _close(max(ys), origin[1])
        ):
            raise SmokeVerificationError("TB line-grid extents postcondition failed")

        _undo_and_wait(
            doc,
            lambda: all(_entity_by_handle(doc, handle) is None for handle in adapter_result.created_handles),
            timeout=timeout,
        )
        _undo_and_wait(
            doc,
            lambda: _model_handles(doc) == baseline and not _layer_exists(doc, layer_name),
            timeout=timeout,
        )
        return _result(
            alias,
            layer_name,
            baseline,
            _model_handles(doc),
            adapter_result=adapter_result.model_dump(mode="json"),
            verified_attributes={
                "object_name": "AcDbLine",
                "line_count": 6,
                "width": 2200.0,
                "height": 1400.0,
            },
        )
    except Exception:
        _cleanup_direct(doc, layer_name)
        raise


def _run_tbt(doc: Any, *, timeout: float, origin: tuple[float, float]) -> dict[str, Any]:
    alias, layer_name = "TBT", _new_layer_name("TBT")
    baseline = _model_handles(doc)
    table = None
    try:
        _begin_setup(doc)
        try:
            _setup_layer(doc, layer_name)
            table = doc.ModelSpace.AddTable(_point(origin[0], origin[1]), 2, 2, 600.0, 1200.0)
            table.Layer = layer_name
            table.SetText(1, 1, "")
        finally:
            _end_setup(doc)

        table_handle = str(table.Handle)
        expected_text = "HSCAD-SMOKE-CELL"
        request = TableTextRequest(
            document_id=DOCUMENT_NAME,
            table_handle=table_handle,
            cells=(TableTextCell(row=1, column=1, text=expected_text),),
            overwrite_nonempty=False,
        )
        preview = preview_live_tbt(request)
        execution = LiveTbtExecuteRequest(
            request=request,
            expected_table=LiveTableEvidence.model_validate(preview["expected_table"]),
            approval_fingerprint=preview["approval_fingerprint"],
        )
        adapter_result = execute_live_tbt(execution)
        current = _entity_by_handle(doc, table_handle)
        if (
            current is None
            or str(current.ObjectName).casefold() != "acdbtable"
            or str(current.GetText(1, 1)) != expected_text
            or str(current.Layer).casefold() != layer_name.casefold()
        ):
            raise SmokeVerificationError("TBT cell-text postcondition failed")

        _undo_and_wait(
            doc,
            lambda: (entity := _entity_by_handle(doc, table_handle)) is not None and str(entity.GetText(1, 1)) == "",
            timeout=timeout,
        )
        _undo_and_wait(
            doc,
            lambda: _model_handles(doc) == baseline and not _layer_exists(doc, layer_name),
            timeout=timeout,
        )
        return _result(
            alias,
            layer_name,
            baseline,
            _model_handles(doc),
            adapter_result=adapter_result.model_dump(mode="json"),
            verified_attributes={"object_name": "AcDbTable", "row": 1, "column": 1, "text": expected_text},
        )
    except Exception:
        _cleanup_direct(doc, layer_name)
        raise


def _run_rr(doc: Any, *, timeout: float, origin: tuple[float, float]) -> dict[str, Any]:
    alias, layer_name = "RR", _new_layer_name("RR")
    baseline = _model_handles(doc)
    text = None
    original_point = (origin[0] + 1000.0, origin[1], 0.0)
    expected_point = (origin[0], origin[1] + 1000.0, 0.0)
    digest_before = "sha256:" + "a" * 64
    digest_after = "sha256:" + "b" * 64
    try:
        _begin_setup(doc)
        try:
            _setup_layer(doc, layer_name)
            text = doc.ModelSpace.AddText("HSCAD-SMOKE-RR", _point(*original_point), 250.0)
            text.Layer = layer_name
            text.Rotation = 0.0
        finally:
            _end_setup(doc)

        handle = str(text.Handle)
        source = EntitySnapshot(
            handle=handle,
            revision=f"smoke-{handle}",
            entity_type="AcDbText",
            state_digest=digest_before,
        )
        exact_changes = ExactChangeSet(
            source_revisions=(source.revision,),
            created_or_updated=(
                ExactEntityResult(
                    result_id=handle,
                    entity_type="AcDbText",
                    layer=layer_name,
                    state_digest=digest_after,
                ),
            ),
            manifest_digest=digest_after,
        )
        request = ReferenceRotateRequest(
            document_id=DOCUMENT_NAME,
            sources=(source,),
            base_point=RRPoint3D(x=origin[0], y=origin[1]),
            reference_start=RRPoint3D(x=origin[0], y=origin[1]),
            reference_end=RRPoint3D(x=origin[0] + 1000.0, y=origin[1]),
            destination_start=RRPoint3D(x=origin[0], y=origin[1]),
            destination_end=RRPoint3D(x=origin[0], y=origin[1] + 1000.0),
            exact_changes=exact_changes,
        )
        preview = preview_live_rr(request)
        execution = LiveRRExecuteRequest(
            request=request,
            expected_sources=tuple(LiveRREntityEvidence.model_validate(item) for item in preview["expected_sources"]),
            approval_fingerprint=preview["approval_fingerprint"],
        )
        adapter_result = execute_live_rr(execution)
        current = _entity_by_handle(doc, handle)
        if (
            current is None
            or not _same_point(current.InsertionPoint, expected_point)
            or not _close(float(current.Rotation), 1.5707963267948966)
            or str(current.Layer).casefold() != layer_name.casefold()
        ):
            raise SmokeVerificationError("RR text rotation postcondition failed")

        _undo_and_wait(
            doc,
            lambda: (
                (entity := _entity_by_handle(doc, handle)) is not None
                and _same_point(entity.InsertionPoint, original_point)
                and _close(float(entity.Rotation), 0.0)
            ),
            timeout=timeout,
        )
        _undo_and_wait(
            doc,
            lambda: _model_handles(doc) == baseline and not _layer_exists(doc, layer_name),
            timeout=timeout,
        )
        return _result(
            alias,
            layer_name,
            baseline,
            _model_handles(doc),
            adapter_result=adapter_result.model_dump(mode="json"),
            verified_attributes={
                "object_name": "AcDbText",
                "rotation_delta_radians": 1.5707963267948966,
                "insertion_point": expected_point,
            },
        )
    except Exception:
        _cleanup_direct(doc, layer_name)
        raise


def _selected_scenarios(values: Iterable[str]) -> tuple[str, ...]:
    selected = tuple(dict.fromkeys(value.casefold() for value in values))
    unknown = sorted(set(selected) - set(SCENARIOS))
    if unknown:
        raise ValueError(f"unknown scenarios: {', '.join(unknown)}")
    if not selected:
        raise ValueError("at least one scenario is required")
    return selected


def verify(*, scenarios: tuple[str, ...] = SCENARIOS, timeout: float = 15.0) -> dict[str, Any]:
    import win32com.client

    selected = _selected_scenarios(scenarios)
    app = win32com.client.GetActiveObject(PROG_ID)
    doc = _exact_document(app)
    doc.Activate()
    if not _is_idle(doc):
        raise SmokeVerificationError(f"Drawing1 CMDACTIVE must be 0, got {doc.GetVariable('CMDACTIVE')}")

    started = datetime.now(timezone.utc)
    baseline_handles = _model_handles(doc)
    runners = {
        "ct": _run_ct,
        "dts": _run_dts,
        "flt": _run_flt,
        "sol": _run_sol,
        "tb": _run_tb,
        "tbt": _run_tbt,
        "rr": _run_rr,
    }
    results: list[dict[str, Any]] = []
    for ordinal, scenario in enumerate(selected):
        origin = _scenario_origin(doc, ordinal)
        try:
            results.append(runners[scenario](doc, timeout=timeout, origin=origin))
        except Exception as exc:
            results.append(
                {
                    "alias": scenario.upper(),
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "postcondition_verified": False,
                    "undo_restored": _model_handles(doc) == baseline_handles,
                }
            )

    final_handles = _model_handles(doc)
    final_idle = _is_idle(doc)
    all_passed = (
        all(result["status"] == "passed" and result["undo_restored"] for result in results)
        and final_handles == baseline_handles
        and final_idle
    )
    finished = datetime.now(timezone.utc)
    return {
        "schema_version": 1,
        "document": str(doc.Name),
        "program_id": PROG_ID,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round((finished - started).total_seconds(), 6),
        "preflight": {
            "exact_document_match": str(doc.Name) == DOCUMENT_NAME,
            "cmdactive": 0,
            "baseline_object_count": len(baseline_handles),
            "save_invoked": False,
        },
        "scenarios": results,
        "final": {
            "object_count": len(final_handles),
            "object_count_restored": len(final_handles) == len(baseline_handles),
            "handles_restored": final_handles == baseline_handles,
            "cmdactive": int(doc.GetVariable("CMDACTIVE")),
            "idle": final_idle,
        },
        "passed": all_passed,
    }


def _write_json(result: dict[str, Any], output: Path | None) -> None:
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    print(payload)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        action="append",
        choices=SCENARIOS,
        dest="scenarios",
        help="Run one scenario (repeatable); default: all seven scenarios",
    )
    parser.add_argument("--timeout", type=float, default=15.0, help="Undo/postcondition timeout in seconds")
    parser.add_argument("--output", type=Path, help="Optional JSON result path")
    args = parser.parse_args()
    try:
        result = verify(scenarios=tuple(args.scenarios or SCENARIOS), timeout=args.timeout)
    except Exception as exc:
        result = {
            "schema_version": 1,
            "document": DOCUMENT_NAME,
            "program_id": PROG_ID,
            "passed": False,
            "fatal_error": {"type": type(exc).__name__, "message": str(exc)},
        }
    _write_json(result, args.output)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
