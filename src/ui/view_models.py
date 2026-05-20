from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DWGFileState:
    path: Path | None = None
    exists: bool = False
    object_count: int = 0


@dataclass
class XiCADState:
    root: Path | None = None
    detected: bool = False
    catalog_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class ScanResultState:
    layers: int = 0
    blocks: int = 0
    texts: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class CommandPreviewState:
    raw_command: dict[str, Any] | None = None
    planned_actions: list[dict[str, Any]] = field(default_factory=list)
    can_execute: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExecutionResultState:
    executed: bool = False
    saved_as: Path | None = None
    created: int = 0
    changed: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ReportState:
    output_dir: Path | None = None
    files: dict[str, Path] = field(default_factory=dict)


@dataclass
class ProjectState:
    dwg: DWGFileState = field(default_factory=DWGFileState)
    xicad: XiCADState = field(default_factory=XiCADState)
    scan: ScanResultState = field(default_factory=ScanResultState)
    preview: CommandPreviewState = field(default_factory=CommandPreviewState)
    execution: ExecutionResultState = field(default_factory=ExecutionResultState)
    report: ReportState = field(default_factory=ReportState)
