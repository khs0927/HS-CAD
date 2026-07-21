from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.headless_core.wal_core import WALInput, execute_wal


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


def _drawing(adapter: ZWCADCOMAdapter, document_name: str) -> Any:
    adapter.connect()
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
