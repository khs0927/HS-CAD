"""Help-verified live promotions for xiCAD batches 17 through 24.

This module deliberately contains only commands whose recovered structured
contract describes the same mutation as the public xiCAD help.  Commands for
which the contract would produce only a visual approximation remain blocked in
their original live batch.

TAJ evidence:
* xiCAD help: https://izzarder.com/305
* AutoCAD ActiveX GetColumnWidth:
  https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-ActiveX-Reference/files/GUID-75753472-516B-46B4-B8BB-C8E7FDA58F42.htm
* AutoCAD ActiveX SetColumnWidth:
  https://help.autodesk.com/cloudhelp/2025/ENU/AutoCAD-ActiveX-Reference/files/GUID-F9800295-53CB-4D8E-B786-DBA53A526DE1.htm
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch18 import CadTableSnapshot, TableWidthRequest, plan_table_width

XI_HELP_TAJ = "https://izzarder.com/305"
AUTODESK_GET_COLUMN_WIDTH = (
    "https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-ActiveX-Reference/files/"
    "GUID-75753472-516B-46B4-B8BB-C8E7FDA58F42.htm"
)
AUTODESK_SET_COLUMN_WIDTH = (
    "https://help.autodesk.com/cloudhelp/2025/ENU/AutoCAD-ActiveX-Reference/files/"
    "GUID-F9800295-53CB-4D8E-B786-DBA53A526DE1.htm"
)


class LiveTajTableEvidence(BaseModel):
    """Complete state needed to reject stale or unsafe TAJ execution."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    handle: str = Field(min_length=1)
    object_name: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    locked_layer: bool
    is_xref: bool
    row_count: int = Field(gt=0)
    column_count: int = Field(gt=0)
    cells: tuple[tuple[str, ...], ...] = Field(min_length=1)
    column_widths: tuple[float, ...] = Field(min_length=1)
    text_height: float = Field(gt=0)
    state_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveTajPreviewRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_name: str = Field(min_length=1)
    request: TableWidthRequest


class LiveTajExecuteRequest(LiveTajPreviewRequest):
    expected_tables: tuple[LiveTajTableEvidence, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveGap1724Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_name: str
    command_alias: str
    changed_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    rollback_performed: bool
    postcondition_verified: bool


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _drawing(name: str) -> Any:
    import win32com.client

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [document for document in app.Documents if str(document.Name).casefold() == name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {name!r}, found {len(matches)}")
    matches[0].Activate()
    return matches[0]


def _entities(doc: Any) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    for block in doc.Blocks:
        if bool(block.IsLayout):
            for entity in block:
                handle = str(entity.Handle)
                folded = handle.casefold()
                if folded in entities:
                    raise RuntimeError(f"duplicate top-level entity handle in drawing: {handle}")
                entities[folded] = entity
    return entities


def _layer_state(doc: Any, layer_name: str) -> tuple[bool, bool]:
    try:
        layer = doc.Layers.Item(layer_name)
    except Exception as exc:
        raise ValueError(f"TAJ table layer no longer exists: {layer_name}") from exc
    actual_name = str(layer.Name)
    return bool(layer.Lock), "|" in actual_name


def _cell_text_height(table: Any, row: int, column: int) -> float:
    """Read an actual cell text height without silently inventing a default."""

    readers = (
        lambda: table.GetCellTextHeight(row, column),
        lambda: table.GetTextHeight(row, column),
        lambda: table.GetTextHeight(row),
    )
    for reader in readers:
        try:
            value = float(reader())
        except Exception:
            continue
        if value > 0:
            return value
    raise ValueError(f"TAJ cannot read a positive text height for table {table.Handle}, cell ({row}, {column})")


def _table_evidence(doc: Any, handle: str) -> tuple[LiveTajTableEvidence, Any]:
    table = _entities(doc).get(handle.casefold())
    if table is None:
        raise ValueError(f"TAJ table does not exist: {handle}")
    object_name = str(table.ObjectName)
    if object_name.casefold() != "acdbtable":
        raise ValueError(f"TAJ requires an existing AcDbTable: {handle} is {object_name}")

    layer_name = str(table.Layer)
    locked, is_xref = _layer_state(doc, layer_name)
    if locked or is_xref:
        raise ValueError(f"TAJ refuses locked or xref-dependent table: {handle}")

    rows = int(table.Rows)
    columns = int(table.Columns)
    if rows <= 0 or columns <= 0:
        raise ValueError(f"TAJ requires a non-empty table: {handle}")
    cells = tuple(tuple(str(table.GetText(row, column)) for column in range(columns)) for row in range(rows))
    widths = tuple(float(table.GetColumnWidth(column)) for column in range(columns))
    if any(width <= 0 for width in widths):
        raise ValueError(f"TAJ found a non-positive column width: {handle}")
    heights = tuple(_cell_text_height(table, row, column) for row in range(rows) for column in range(columns))
    # The recovered headless contract has one table-level height, while a real
    # AcDbTable commonly has different title/header/data heights.  Use the
    # greatest observed height so no cell is under-sized.  The cell matrix and
    # chosen height are fingerprint-bound, so a style/content change still
    # becomes a stale-state rejection.
    text_height = max(heights)

    state_payload = {
        "handle": str(table.Handle),
        "object_name": object_name,
        "layer": layer_name,
        "locked_layer": locked,
        "is_xref": is_xref,
        "row_count": rows,
        "column_count": columns,
        "cells": cells,
        "column_widths": widths,
        "text_height": text_height,
    }
    evidence = LiveTajTableEvidence(
        **state_payload,
        state_fingerprint=_fingerprint(state_payload),
    )
    return evidence, table


def _snapshot(evidence: LiveTajTableEvidence) -> CadTableSnapshot:
    return CadTableSnapshot(
        handle=evidence.handle,
        cells=evidence.cells,
        column_widths=evidence.column_widths,
        text_height=evidence.text_height,
        locked_layer=evidence.locked_layer,
    )


def _payload(
    wrapper: LiveTajPreviewRequest,
    tables: tuple[LiveTajTableEvidence, ...],
) -> dict[str, Any]:
    snapshots = tuple(_snapshot(table) for table in tables)
    plan = plan_table_width(wrapper.request, snapshots)
    return {
        "command_alias": "TAJ",
        "document_name": wrapper.document_name,
        "request": wrapper.request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "expected_tables": [table.model_dump(mode="json") for table in tables],
        "semantic_evidence": {
            "xicad_help": XI_HELP_TAJ,
            "activex_get_column_width": AUTODESK_GET_COLUMN_WIDTH,
            "activex_set_column_width": AUTODESK_SET_COLUMN_WIDTH,
        },
    }


def _validate_wrapper(wrapper: LiveTajPreviewRequest) -> None:
    if wrapper.request.document_id.casefold() != wrapper.document_name.casefold():
        raise ValueError("request document_id must exactly match document_name")
    if not wrapper.request.dry_run:
        raise ValueError("live preview and execute wrappers require the structured request in dry-run mode")
    folded = [handle.casefold() for handle in wrapper.request.table_handles]
    if len(folded) != len(set(folded)):
        raise ValueError("TAJ table handles must be unique")


def preview_live_taj(request: LiveTajPreviewRequest) -> dict[str, Any]:
    """Capture the exact table state and return an approval-bound TAJ plan."""

    _validate_wrapper(request)
    doc = _drawing(request.document_name)
    tables = tuple(_table_evidence(doc, handle)[0] for handle in request.request.table_handles)
    payload = _payload(request, tables)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "scope_note": "official TAJ: resize existing CAD-table columns to their current cell text",
    }


def _restore_widths(
    tables: tuple[tuple[Any, LiveTajTableEvidence], ...],
) -> None:
    errors: list[str] = []
    for table, evidence in reversed(tables):
        for column, width in enumerate(evidence.column_widths):
            try:
                table.SetColumnWidth(column, width)
            except Exception as exc:  # pragma: no cover - COM failure reporting
                errors.append(f"{evidence.handle}[{column}]: {exc}")
        try:
            table.Update()
        except Exception:
            pass
    if errors:
        raise RuntimeError("TAJ rollback was incomplete: " + "; ".join(errors))


def execute_live_taj(request: LiveTajExecuteRequest) -> LiveGap1724Result:
    """Execute an approval-bound TAJ mutation with stale-state rejection."""

    _validate_wrapper(request)
    expected_by_handle = {table.handle.casefold(): table for table in request.expected_tables}
    requested_handles = tuple(handle.casefold() for handle in request.request.table_handles)
    if len(expected_by_handle) != len(request.expected_tables) or set(expected_by_handle) != set(requested_handles):
        raise ValueError("TAJ expected_tables must contain exactly one entry for every requested handle")

    ordered_expected = tuple(expected_by_handle[handle] for handle in requested_handles)
    payload = _payload(request, ordered_expected)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact TAJ plan and table state")

    doc = _drawing(request.document_name)
    current: list[tuple[Any, LiveTajTableEvidence]] = []
    for expected in ordered_expected:
        observed, table = _table_evidence(doc, expected.handle)
        if observed != expected:
            raise ValueError(f"TAJ table state is stale: {expected.handle}")
        current.append((table, expected))

    plan = plan_table_width(request.request, tuple(_snapshot(item) for item in ordered_expected))
    opened = False
    closed = False
    rollback_performed = False
    doc.StartUndoMark()
    opened = True
    try:
        for table, evidence in current:
            widths = plan.widths_by_handle[evidence.handle]
            for column, width in enumerate(widths):
                table.SetColumnWidth(column, width)
            try:
                table.Update()
            except Exception:
                pass
    except Exception:
        rollback_performed = True
        _restore_widths(tuple(current))
        raise
    finally:
        doc.EndUndoMark()
        closed = True

    try:
        for table, evidence in current:
            expected_widths = plan.widths_by_handle[evidence.handle]
            observed_widths = tuple(float(table.GetColumnWidth(column)) for column in range(evidence.column_count))
            if len(observed_widths) != len(expected_widths) or any(
                abs(observed - expected) > max(1e-8, abs(expected) * 1e-8)
                for observed, expected in zip(observed_widths, expected_widths, strict=True)
            ):
                raise RuntimeError(f"TAJ width postcondition failed: {evidence.handle}")
            if (
                tuple(
                    tuple(str(table.GetText(row, column)) for column in range(evidence.column_count))
                    for row in range(evidence.row_count)
                )
                != evidence.cells
            ):
                raise RuntimeError(f"TAJ changed table text unexpectedly: {evidence.handle}")
            locked, is_xref = _layer_state(doc, str(table.Layer))
            if (
                str(table.Handle).casefold() != evidence.handle.casefold()
                or str(table.ObjectName).casefold() != "acdbtable"
                or str(table.Layer).casefold() != evidence.layer.casefold()
                or locked
                or is_xref
            ):
                raise RuntimeError(f"TAJ identity/layer postcondition failed: {evidence.handle}")
    except Exception:
        rollback_performed = True
        _restore_widths(tuple(current))
        raise

    return LiveGap1724Result(
        document_name=str(doc.Name),
        command_alias="TAJ",
        changed_handles=tuple(evidence.handle for _table, evidence in current),
        undo_mark_opened=opened,
        undo_mark_closed=closed,
        rollback_performed=rollback_performed,
        postcondition_verified=True,
    )


def register_live_gap_17_24_tools(mcp: FastMCP) -> None:
    """Register the help-verified Batch 17-24 live promotion."""

    preview_annotations = ToolAnnotations(
        title="Preview xiCAD TAJ table width adjustment",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute_annotations = ToolAnnotations(
        title="Execute xiCAD TAJ table width adjustment",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    mcp.tool(name="xicad_preview_live_taj", annotations=preview_annotations)(preview_live_taj)
    mcp.tool(name="xicad_execute_live_taj", annotations=execute_annotations)(execute_live_taj)
