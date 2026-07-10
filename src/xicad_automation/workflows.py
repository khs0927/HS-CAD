from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .contracts import ContractLibrary
from .models import CommandStep, WorkflowSpec


class ArchitecturalElement(BaseModel):
    """Semantic building element compiled through a verified XiCAD contract."""

    kind: Literal[
        "wall",
        "door",
        "window",
        "column",
        "beam",
        "stair",
        "elevator",
        "parking",
        "insulation",
        "annotation",
        "custom",
    ]
    alias: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=120.0, ge=1.0, le=3600.0)
    checkpoint: bool = True
    description: str = ""

    @field_validator("alias")
    @classmethod
    def normalize_alias(cls, value: str) -> str:
        return value.strip().upper()


class ArchitecturalDrawingSpec(BaseModel):
    name: str = "XiCAD architectural drawing"
    source_dwg: Path
    working_dwg: Path
    xicad_root: Path
    elements: list[ArchitecturalElement] = Field(min_length=1)
    dry_run: bool = True
    save_after_each_step: bool = True
    keep_recovery_copy: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArchitecturalWorkflowCompiler:
    """Compile semantic building elements into deterministic XiCAD prompt scripts."""

    def __init__(self, contracts: ContractLibrary) -> None:
        self.contracts = contracts

    def compile(self, drawing: ArchitecturalDrawingSpec) -> WorkflowSpec:
        steps: list[CommandStep] = []
        for element in drawing.elements:
            contract = self.contracts.require_verified(element.alias)
            arguments = contract.render(element.parameters)
            steps.append(
                CommandStep(
                    alias=element.alias,
                    arguments=arguments,
                    timeout_seconds=element.timeout_seconds,
                    allow_interactive=True,
                    checkpoint=element.checkpoint,
                    description=element.description or f"{element.kind}: {element.alias}",
                    metadata={"kind": element.kind, "parameters": element.parameters},
                )
            )
        return WorkflowSpec(
            name=drawing.name,
            source_dwg=drawing.source_dwg,
            working_dwg=drawing.working_dwg,
            xicad_root=drawing.xicad_root,
            steps=steps,
            dry_run=drawing.dry_run,
            save_after_each_step=drawing.save_after_each_step,
            keep_recovery_copy=drawing.keep_recovery_copy,
            metadata={**drawing.metadata, "compiler": "architectural-contract-v1"},
        )
