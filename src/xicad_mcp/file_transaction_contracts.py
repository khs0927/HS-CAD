"""Pure safety contracts for future xiCAD file and drawing-resource transactions."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from pathlib import PureWindowsPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval

DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:\\")


class FileOperationKind(StrEnum):
    OPEN_DRAWING = "open_drawing"
    CLOSE_DRAWING = "close_drawing"
    SAVE_AS = "save_as"
    EXPORT = "export"
    PLOT = "plot"
    COPY_RESOURCE = "copy_resource"
    WRITE_TEXT = "write_text"


class OverwritePolicy(StrEnum):
    FORBID = "forbid"
    REQUIRE_MATCH = "require_match"
    REPLACE_ATOMIC = "replace_atomic"


class FileSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    path: str = Field(min_length=3)
    exists: bool
    size_bytes: int | None = Field(default=None, ge=0)
    digest: str | None = Field(default=None, pattern=DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_snapshot(self) -> FileSnapshot:
        canonical_windows_path(self.path)
        if not self.exists and (self.size_bytes is not None or self.digest is not None):
            raise ValueError("missing file snapshots cannot include size or digest")
        if self.exists and self.size_bytes is None:
            raise ValueError("existing file snapshots require size_bytes")
        return self


class DrawingStateSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_name: str = Field(min_length=1)
    full_path: str | None = None
    modified: bool
    active_command_count: int = Field(ge=0)
    open_document_names: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_drawing(self) -> DrawingStateSnapshot:
        if self.full_path is not None:
            canonical_windows_path(self.full_path)
        if self.document_name.casefold() not in {name.casefold() for name in self.open_document_names}:
            raise ValueError("active document must be present in open_document_names")
        return self


class FileTransactionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: FileOperationKind
    allowed_roots: tuple[str, ...] = Field(min_length=1)
    source_path: str | None = None
    destination_path: str | None = None
    overwrite_policy: OverwritePolicy = OverwritePolicy.FORBID
    expected_source: FileSnapshot | None = None
    expected_destination: FileSnapshot | None = None
    expected_drawing: DrawingStateSnapshot | None = None
    close_save_changes: bool | None = None
    dry_run: bool = True
    approval: Approval = Approval()

    @model_validator(mode="after")
    def validate_request(self) -> FileTransactionRequest:
        roots = tuple(canonical_windows_path(root) for root in self.allowed_roots)
        if len(set(roots)) != len(roots):
            raise ValueError("allowed_roots must be unique after canonicalization")

        source_required = self.operation in {
            FileOperationKind.OPEN_DRAWING,
            FileOperationKind.COPY_RESOURCE,
        }
        destination_required = self.operation in {
            FileOperationKind.SAVE_AS,
            FileOperationKind.EXPORT,
            FileOperationKind.PLOT,
            FileOperationKind.COPY_RESOURCE,
            FileOperationKind.WRITE_TEXT,
        }
        drawing_required = self.operation in {
            FileOperationKind.CLOSE_DRAWING,
            FileOperationKind.SAVE_AS,
            FileOperationKind.EXPORT,
            FileOperationKind.PLOT,
        }

        if source_required and self.source_path is None:
            raise ValueError(f"{self.operation} requires source_path")
        if destination_required and self.destination_path is None:
            raise ValueError(f"{self.operation} requires destination_path")
        if drawing_required and self.expected_drawing is None:
            raise ValueError(f"{self.operation} requires expected_drawing")
        if self.operation is FileOperationKind.CLOSE_DRAWING and self.close_save_changes is None:
            raise ValueError("close_drawing requires an explicit close_save_changes decision")
        if self.operation is not FileOperationKind.CLOSE_DRAWING and self.close_save_changes is not None:
            raise ValueError("close_save_changes applies only to close_drawing")

        for path in (self.source_path, self.destination_path):
            if path is not None:
                require_allowed_path(path, self.allowed_roots)

        if self.expected_source is not None:
            if self.source_path is None:
                raise ValueError("expected_source requires source_path")
            if canonical_windows_path(self.expected_source.path) != canonical_windows_path(self.source_path):
                raise ValueError("expected_source path must match source_path")
        if self.expected_destination is not None:
            if self.destination_path is None:
                raise ValueError("expected_destination requires destination_path")
            if canonical_windows_path(self.expected_destination.path) != canonical_windows_path(
                self.destination_path
            ):
                raise ValueError("expected_destination path must match destination_path")

        if self.source_path and self.destination_path:
            if canonical_windows_path(self.source_path) == canonical_windows_path(self.destination_path):
                raise ValueError("source_path and destination_path must differ")

        if self.overwrite_policy is OverwritePolicy.FORBID:
            if self.expected_destination is not None and self.expected_destination.exists:
                raise ValueError("overwrite_policy=forbid requires a missing destination snapshot")
        elif self.overwrite_policy is OverwritePolicy.REQUIRE_MATCH:
            if (
                self.expected_destination is None
                or not self.expected_destination.exists
                or self.expected_destination.digest is None
            ):
                raise ValueError("require_match needs an existing destination snapshot with digest")

        if not self.dry_run and (
            not self.approval.approved or self.approval.fingerprint != self.fingerprint()
        ):
            raise ValueError("file transaction execution requires an exact approval fingerprint")
        return self

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"dry_run", "approval"})
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


class FileTransactionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: FileOperationKind
    canonical_source_path: str | None
    canonical_destination_path: str | None
    temporary_path: str | None
    request_fingerprint: str
    required_preconditions: tuple[str, ...]
    commit_steps: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    live_executable: bool = False
    blocked_reason: str = "adapter and failure-recovery evidence are not implemented"


def canonical_windows_path(value: str) -> str:
    normalized = value.replace("/", "\\").strip()
    if not _DRIVE_PATTERN.match(normalized):
        raise ValueError("file transaction paths must be absolute Windows drive paths")
    path = PureWindowsPath(normalized)
    if ".." in path.parts:
        raise ValueError("file transaction paths cannot contain parent traversal")
    if any(part in {"", "."} for part in path.parts[1:]):
        raise ValueError("file transaction paths cannot contain empty or current-directory segments")
    return str(path).casefold()


def require_allowed_path(path: str, allowed_roots: tuple[str, ...]) -> str:
    canonical = canonical_windows_path(path)
    roots = tuple(canonical_windows_path(root).rstrip("\\") for root in allowed_roots)
    if not any(canonical == root or canonical.startswith(root + "\\") for root in roots):
        raise ValueError(f"path is outside allowed_roots: {path}")
    return canonical


def _temporary_path(destination: str | None, fingerprint: str) -> str | None:
    if destination is None:
        return None
    canonical = canonical_windows_path(destination)
    suffix = fingerprint.removeprefix("sha256:")[:12]
    return f"{canonical}.xicad-txn-{suffix}.tmp"


def plan_file_transaction(request: FileTransactionRequest) -> FileTransactionPlan:
    source = canonical_windows_path(request.source_path) if request.source_path else None
    destination = canonical_windows_path(request.destination_path) if request.destination_path else None
    fingerprint = request.fingerprint()
    temporary = None
    commit_steps: tuple[str, ...]
    rollback_steps: tuple[str, ...]

    if destination is not None:
        temporary = _temporary_path(destination, fingerprint)
        commit_steps = (
            "write or export only to temporary_path",
            "flush and close the temporary file",
            "verify temporary size and digest against the adapter result",
            "atomically replace or create destination_path according to overwrite_policy",
            "verify final destination size and digest",
        )
        rollback_steps = (
            "delete temporary_path when present",
            "restore the original destination when replacement began",
            "verify destination matches expected_destination",
        )
    elif request.operation is FileOperationKind.CLOSE_DRAWING:
        commit_steps = (
            "verify exact drawing state and active command count",
            "close the named drawing with the explicit save decision",
            "verify the drawing is absent and all other open drawings are unchanged",
        )
        rollback_steps = (
            "no automatic reopen is claimed",
            "report close failure without changing truthful state",
        )
    else:
        commit_steps = (
            "verify source snapshot and exact open-document set",
            "perform the bounded open operation",
            "verify exactly one expected document was added",
        )
        rollback_steps = (
            "close only the newly opened document without saving when postconditions fail",
            "verify the original open-document set is restored",
        )

    preconditions = [
        "every path is canonical and inside allowed_roots",
        "source and destination snapshots match size/digest expectations",
        "drawing dirty state and active command count match the approved snapshot",
        "no unapproved overwrite or save decision is inferred",
    ]
    return FileTransactionPlan(
        operation=request.operation,
        canonical_source_path=source,
        canonical_destination_path=destination,
        temporary_path=temporary,
        request_fingerprint=fingerprint,
        required_preconditions=tuple(preconditions),
        commit_steps=commit_steps,
        rollback_steps=rollback_steps,
    )
