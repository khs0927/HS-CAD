"""Bounded live promotion for the unresolved Batch 15/16 aliases.

Only GEE is promoted here.  The existing headless GEE contract describes an
exact, drawing-local group edit whose state is observable through ActiveX and
whose mutation is covered by a drawing Undo mark.

The remaining aliases in this audit are intentionally not registered as live
mutations.  They either change state outside drawing Undo (COM/EXP/OL/ON/QQ),
produce a definition rather than a CAD mutation (BPT), require cross-document
definition cloning with unresolved conflict semantics (STL), or do not yet
define the complete output geometry (CW/D1/D2/D3).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch15 import (
    GroupEditRequest,
    GroupOperation,
    GroupSnapshot,
    plan_group_edit,
)

LIVE_BLOCKED_REASONS: dict[str, str] = {
    "STL": "cross-document definition cloning and conflict replacement are not fully specified by the contract",
    "COM": "shortcut/PGP file mutation is outside drawing Undo",
    "EXP": "Explorer process launch is outside drawing Undo",
    "OL": "opening another document is outside active-drawing Undo",
    "ON": "opening the next document is outside active-drawing Undo",
    "QQ": "saving or closing documents cannot be restored by drawing Undo",
    "BPT": "the approved contract returns a pattern definition and intentionally blocks PAT/file installation",
    "CW": "bar, cap, glass, straight/curved offset, and grouping output geometry is not fully specified",
    "D1": "frame, leaf, swing, wall-cut, and single/double-door output geometry is not fully specified",
    "D2": "detailed frame, leaf, threshold, swing, and wall-cut output geometry is not fully specified",
    "D3": "D3 preset persistence and detailed door output geometry is not fully specified",
}


class LiveGeeExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request: GroupEditRequest
    expected_group: GroupSnapshot
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveGeeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_name: str
    command_alias: str = "GEE"
    original_group_name: str
    resulting_group_name: str
    resulting_member_handles: tuple[str, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _application() -> Any:
    import win32com.client

    for progid in ("ZWCAD.Application.2026", "ZWCAD.Application.2025", "ZWCAD.Application"):
        try:
            return win32com.client.GetActiveObject(progid)
        except Exception:
            continue
    raise RuntimeError("no active ZWCAD application was found")


def _drawing(name: str) -> Any:
    app = _application()
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {name!r}, found {len(matches)}")
    matches[0].Activate()
    return matches[0]


def _collection_items(collection: Any) -> tuple[Any, ...]:
    try:
        return tuple(collection.Item(index) for index in range(int(collection.Count)))
    except Exception:
        return tuple(collection)


def _groups(doc: Any) -> dict[str, Any]:
    return {str(group.Name).casefold(): group for group in _collection_items(doc.Groups)}


def _group_snapshot(group: Any) -> GroupSnapshot:
    members = _collection_items(group)
    return GroupSnapshot(
        name=str(group.Name),
        member_handles=tuple(str(entity.Handle) for entity in members),
    )


def _entities(doc: Any) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    for block in _collection_items(doc.Blocks):
        if bool(block.IsLayout):
            for entity in _collection_items(block):
                entities[str(entity.Handle).casefold()] = entity
    return entities


def _dispatch_array(entities: tuple[Any, ...]) -> Any:
    """Return the VT_DISPATCH SAFEARRAY required by real ZWCAD ActiveX."""

    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, entities)


def _payload(request: GroupEditRequest, expected_group: GroupSnapshot) -> dict[str, Any]:
    return {
        "command_alias": "GEE",
        "request": request.model_dump(mode="json"),
        "expected_group": expected_group.model_dump(mode="json"),
    }


def preview_live_gee(request: GroupEditRequest) -> dict[str, Any]:
    """Preview an exact existing-group edit and bind it to current CAD state."""

    if not request.dry_run:
        raise ValueError("live GEE preview requires the structured request in dry-run mode")
    doc = _drawing(request.document_id)
    group = _groups(doc).get(request.group_name.casefold())
    if group is None:
        raise ValueError(f"GEE group not found: {request.group_name}")
    snapshot = _group_snapshot(group)

    entity_map = _entities(doc)
    missing = tuple(handle for handle in request.member_handles if handle.casefold() not in entity_map)
    if missing:
        raise ValueError(f"GEE target handles are unavailable: {', '.join(missing)}")
    if request.operation is GroupOperation.RENAME:
        assert request.new_name is not None
        collision = _groups(doc).get(request.new_name.casefold())
        if collision is not None and collision is not group:
            raise ValueError(f"GEE resulting group name already exists: {request.new_name}")

    plan = plan_group_edit(request, (snapshot,))
    payload = _payload(request, snapshot)
    return {
        **payload,
        "resulting_group_name": plan.resulting_name,
        "resulting_member_handles": plan.resulting_members,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "scope_note": "existing-group add/remove/rename only; one drawing Undo mark",
    }


def execute_live_gee(request: LiveGeeExecuteRequest) -> LiveGeeResult:
    """Execute the approved group edit and verify its complete resulting state."""

    payload = _payload(request.request, request.expected_group)
    if request.approval_fingerprint != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact GEE request")

    doc = _drawing(request.request.document_id)
    group = _groups(doc).get(request.request.group_name.casefold())
    if group is None or _group_snapshot(group) != request.expected_group:
        raise ValueError("GEE group state no longer matches the approved plan")

    entity_map = _entities(doc)
    selected: list[Any] = []
    for handle in request.request.member_handles:
        entity = entity_map.get(handle.casefold())
        if entity is None:
            raise ValueError(f"GEE target handle is no longer available: {handle}")
        selected.append(entity)

    plan = plan_group_edit(request.request, (request.expected_group,))
    if request.request.operation is GroupOperation.RENAME:
        collision = _groups(doc).get(plan.resulting_name.casefold())
        if collision is not None and collision is not group:
            raise ValueError(f"GEE resulting group name already exists: {plan.resulting_name}")

    opened = False
    closed = False
    doc.StartUndoMark()
    opened = True
    try:
        if request.request.operation is GroupOperation.ADD_MEMBERS:
            group.AppendItems(_dispatch_array(tuple(selected)))
        elif request.request.operation is GroupOperation.REMOVE_MEMBERS:
            group.RemoveItems(_dispatch_array(tuple(selected)))
        else:
            group.Name = plan.resulting_name
    finally:
        doc.EndUndoMark()
        closed = True

    result_group = _groups(doc).get(plan.resulting_name.casefold())
    if result_group is None:
        raise RuntimeError("GEE postcondition failed: resulting group is unavailable")
    actual = _group_snapshot(result_group)
    expected_handles = {handle.casefold() for handle in plan.resulting_members}
    actual_handles = {handle.casefold() for handle in actual.member_handles}
    if (
        actual.name.casefold() != plan.resulting_name.casefold()
        or actual_handles != expected_handles
        or len(actual.member_handles) != len(plan.resulting_members)
    ):
        raise RuntimeError("GEE postcondition failed: resulting name or membership differs from the approved plan")

    return LiveGeeResult(
        document_name=str(doc.Name),
        original_group_name=request.expected_group.name,
        resulting_group_name=actual.name,
        resulting_member_handles=actual.member_handles,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
        postcondition_verified=True,
    )


def register_live_gap_15_16_next_tools(mcp: FastMCP) -> None:
    preview_annotations = ToolAnnotations(
        title="Preview live xiCAD GEE group edit",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    execute_annotations = ToolAnnotations(
        title="Execute live xiCAD GEE group edit",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    mcp.tool(name="xicad_preview_live_gee", annotations=preview_annotations)(preview_live_gee)
    mcp.tool(name="xicad_execute_live_gee", annotations=execute_annotations)(execute_live_gee)
