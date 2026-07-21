from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.headless_core.wal_core import WALInput, execute_wal

from .headless_core_batch5 import TextChange, TextHeightChange


class LiveWalPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)
    wall: WALInput

    def fingerprint(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


class LiveWalExecuteRequest(LiveWalPreviewRequest):
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        preview = LiveWalPreviewRequest(document_name=self.document_name, wall=self.wall)
        return preview.fingerprint()


class LiveWalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    created_handles: tuple[str, ...]
    before_count: int
    after_count: int
    postcondition_verified: bool


class LiveTextCommand(StrEnum):
    COI = "COI"
    COR = "COR"
    NUC = "NUC"
    FAR = "FAR"
    TAP = "TAP"
    TS = "TS"


class LiveTextMutationPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str = Field(min_length=1)
    command_alias: LiveTextCommand
    changes: tuple[TextChange, ...] = ()
    height_changes: tuple[TextHeightChange, ...] = ()

    def fingerprint(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


class LiveTextMutationExecuteRequest(LiveTextMutationPreviewRequest):
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return LiveTextMutationPreviewRequest(**self.model_dump(exclude={"approval_fingerprint"})).fingerprint()


class LiveTextMutationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_name: str
    command_alias: LiveTextCommand
    changed_handles: tuple[str, ...]
    postcondition_verified: bool


def _drawing(adapter: ZWCADCOMAdapter, document_name: str) -> Any:
    if adapter.app is None:
        import win32com.client

        adapter.app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
        adapter.active_progid = "ZWCAD.Application.2026"
    matches = [doc for doc in adapter.app.Documents if doc.Name.casefold() == document_name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {document_name!r}, found {len(matches)}")
    adapter.doc = matches[0]
    adapter.doc.Activate()
    return adapter.doc


def preview_live_wal(request: LiveWalPreviewRequest) -> dict[str, Any]:
    return {
        "document_name": request.document_name,
        "wall": request.wall.model_dump(mode="json"),
        "approval_fingerprint": request.fingerprint(),
        "mutation": True,
        "undo_required_for_smoke_test": True,
    }


def _objects_by_handle(doc: Any) -> dict[str, Any]:
    return {str(obj.Handle).casefold(): obj for obj in doc.ModelSpace}


def _validate_text_preconditions(doc: Any, request: LiveTextMutationPreviewRequest) -> dict[str, Any]:
    objects = _objects_by_handle(doc)
    expected_handles = [change.handle for change in request.changes]
    expected_handles.extend(change.handle for change in request.height_changes)
    if len({handle.casefold() for handle in expected_handles}) != len(expected_handles):
        raise ValueError("text mutation handles must be unique across all changes")
    for change in request.changes:
        obj = objects.get(change.handle.casefold())
        if obj is None:
            raise ValueError(f"text handle not found: {change.handle}")
        current = str(obj.TextString)
        if current != change.expected_text:
            raise ValueError(
                f"text precondition failed for {change.handle}: expected {change.expected_text!r}, found {current!r}"
            )
    for change in request.height_changes:
        obj = objects.get(change.handle.casefold())
        if obj is None:
            raise ValueError(f"text handle not found: {change.handle}")
        current = float(obj.Height)
        if abs(current - change.expected_height) > 1e-9:
            raise ValueError(
                f"height precondition failed for {change.handle}: expected {change.expected_height}, found {current}"
            )
    return objects


def preview_live_text_mutation(request: LiveTextMutationPreviewRequest) -> dict[str, Any]:
    if not request.changes and not request.height_changes:
        raise ValueError("live text mutation requires at least one change")
    adapter = ZWCADCOMAdapter(visible=True, version="2026", start_if_needed=False)
    doc = _drawing(adapter, request.document_name)
    _validate_text_preconditions(doc, request)
    return {
        "document_name": doc.Name,
        "command_alias": request.command_alias,
        "change_count": len(request.changes) + len(request.height_changes),
        "approval_fingerprint": request.fingerprint(),
        "mutation": True,
    }


def execute_live_text_mutation(
    request: LiveTextMutationExecuteRequest,
    *,
    allowed_alias: LiveTextCommand,
) -> LiveTextMutationResult:
    if request.command_alias is not allowed_alias:
        raise ValueError(f"this tool only executes {allowed_alias}")
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact text mutation request")
    adapter = ZWCADCOMAdapter(visible=True, version="2026", start_if_needed=False)
    doc = _drawing(adapter, request.document_name)
    objects = _validate_text_preconditions(doc, request)
    doc.StartUndoMark()
    try:
        for change in request.changes:
            objects[change.handle.casefold()].TextString = change.replacement_text
        for change in request.height_changes:
            objects[change.handle.casefold()].Height = change.replacement_height
    finally:
        doc.EndUndoMark()
    objects = _objects_by_handle(doc)
    for change in request.changes:
        if str(objects[change.handle.casefold()].TextString) != change.replacement_text:
            raise RuntimeError(f"text postcondition failed for {change.handle}")
    for change in request.height_changes:
        actual = float(objects[change.handle.casefold()].Height)
        if abs(actual - change.replacement_height) > 1e-9:
            raise RuntimeError(f"height postcondition failed for {change.handle}")
    handles = tuple(change.handle for change in request.changes) + tuple(
        change.handle for change in request.height_changes
    )
    return LiveTextMutationResult(
        document_name=doc.Name,
        command_alias=request.command_alias,
        changed_handles=handles,
        postcondition_verified=True,
    )


def execute_live_wal(request: LiveWalExecuteRequest) -> LiveWalResult:
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact WAL request")
    adapter = ZWCADCOMAdapter(visible=True, version="2026", start_if_needed=False)
    doc = _drawing(adapter, request.document_name)
    before_handles = {str(obj.Handle) for obj in doc.ModelSpace}
    doc.StartUndoMark()
    try:
        created = tuple(str(handle) for handle in execute_wal(adapter, request.wall))
    finally:
        doc.EndUndoMark()
    after_handles = {str(obj.Handle) for obj in doc.ModelSpace}
    verified = bool(created) and all(handle in after_handles for handle in created)
    if not verified:
        raise RuntimeError("WAL postcondition failed: one or more created handles are absent")
    return LiveWalResult(
        document_name=doc.Name,
        created_handles=created,
        before_count=len(before_handles),
        after_count=len(after_handles),
        postcondition_verified=True,
    )


def register_live_zwcad_tools(mcp: FastMCP) -> None:
    mcp.tool(
        name="xicad_preview_live_wal",
        description="Create the exact approval fingerprint for a WAL mutation in one named open ZWCAD drawing.",
        annotations=ToolAnnotations(
            title="Preview live xiCAD WAL",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )(preview_live_wal)
    mcp.tool(
        name="xicad_execute_live_wal",
        description="Execute dialog-free WAL geometry through ZWCAD COM after exact fingerprint approval.",
        annotations=ToolAnnotations(
            title="Execute live xiCAD WAL",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )(execute_live_wal)

    mcp.tool(
        name="xicad_preview_live_text_mutation",
        description="Validate current ZWCAD text values and create an exact approval fingerprint.",
        annotations=ToolAnnotations(
            title="Preview live xiCAD text mutation",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )(preview_live_text_mutation)

    live_write = ToolAnnotations(
        title="Execute live xiCAD text mutation",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )

    def register_text_executor(alias: LiveTextCommand) -> None:
        def execute(request: LiveTextMutationExecuteRequest) -> LiveTextMutationResult:
            return execute_live_text_mutation(request, allowed_alias=alias)

        execute.__name__ = f"execute_live_{alias.value.lower()}"
        mcp.tool(
            name=f"xicad_execute_live_{alias.value.lower()}",
            description=f"Execute dialog-free {alias.value} text changes in one named open ZWCAD drawing.",
            annotations=live_write,
        )(execute)

    for command_alias in LiveTextCommand:
        register_text_executor(command_alias)
