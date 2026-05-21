from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Union

from pydantic import BaseModel, Field

from src.extensions.xicad_safe_bridge.models import XicadSafeCommand


class SafetyOptions(BaseModel):
    backup_required: bool = True
    preview_required: bool = True


class BaseCommand(BaseModel):
    command: str
    safety: SafetyOptions = Field(default_factory=SafetyOptions)


class ScanCommand(BaseCommand):
    command: Literal['scan_all','scan_layers','scan_blocks','scan_texts','export_objects_json','generate_quantity_report','analyze_architecture']
    params: dict[str, Any] = Field(default_factory=dict)


class SaveAsParams(BaseModel):
    path: str
class SaveAsCommand(BaseCommand):
    command: Literal['save_as']
    params: SaveAsParams


class MoveLayerParams(BaseModel):
    layer: str
    dx: float = 0
    dy: float = 0
    dz: float = 0
class MoveLayerCommand(BaseCommand):
    command: Literal['move_layer']
    params: MoveLayerParams


class MoveObjectParams(BaseModel):
    handle: str
    dx: float = 0
    dy: float = 0
    dz: float = 0
class MoveObjectCommand(BaseCommand):
    command: Literal['move_object_by_handle']
    params: MoveObjectParams


class ReplaceTextParams(BaseModel):
    find: str
    replace: str
    layer: str | None = None
class ReplaceTextCommand(BaseCommand):
    command: Literal['replace_text']
    params: ReplaceTextParams


class ReplaceBlockParams(BaseModel):
    target_block: str
    new_block: str
    layer: str | None = None
class ReplaceBlockCommand(BaseCommand):
    command: Literal['replace_block']
    params: ReplaceBlockParams


class DeleteLayerParams(BaseModel):
    layer: str
class DeleteLayerCommand(BaseCommand):
    command: Literal['delete_layer_objects']
    params: DeleteLayerParams


class CreateBoundaryParams(BaseModel):
    width: float
    depth: float
    origin: tuple[float, float, float] = (0,0,0)
    layer: str = 'A-BOUNDARY'
class CreateBoundaryCommand(BaseCommand):
    command: Literal['create_boundary']
    params: CreateBoundaryParams


class CreateGridParams(BaseModel):
    width: float
    depth: float
    grid_x: float
    grid_y: float
    origin: tuple[float, float, float] = (0,0,0)
    layer: str = 'A-GRID'
class CreateGridCommand(BaseCommand):
    command: Literal['create_grid']
    params: CreateGridParams


class PlaceColumnsParams(BaseModel):
    block_name: str
    width: float
    depth: float
    grid_x: float
    grid_y: float
    origin: tuple[float, float, float] = (0,0,0)
    layer: str = 'A-COLUMN'
class PlaceColumnsCommand(BaseCommand):
    command: Literal['place_columns']
    params: PlaceColumnsParams


class PlaceBeams2DParams(BaseModel):
    width: float
    depth: float
    grid_x: float
    grid_y: float
    origin: tuple[float, float, float] = (0,0,0)
    layer: str = 'A-BEAM'
class PlaceBeams2DCommand(BaseCommand):
    command: Literal['place_beams_2d']
    params: PlaceBeams2DParams


class LoadXiCADParams(BaseModel):
    xicad_root: str
class LoadXiCADCommand(BaseCommand):
    command: Literal['load_xicad']
    params: LoadXiCADParams


class DetectXiCADParams(BaseModel):
    xicad_root: str
class DetectXiCADCommand(BaseCommand):
    command: Literal['detect_xicad','build_xicad_catalog']
    params: DetectXiCADParams


class RunXiCADParams(BaseModel):
    alias: str
    xicad_root: str | None = None
    args: list[str] = Field(default_factory=list)
    interactive: bool = True
class RunXiCADCommand(BaseCommand):
    command: Literal['run_xicad_command']
    params: RunXiCADParams


class XiCADWorkflowParams(BaseModel):
    workflow: str
    xicad_root: str | None = None
class XiCADWorkflowCommand(BaseCommand):
    command: Literal['xicad_workflow','run_xicad_workflow']
    params: XiCADWorkflowParams


class DraftSectionDetailsParams(BaseModel):
    base_x: float
    base_y: float
class DraftSectionDetailsCommand(BaseCommand):
    command: Literal['draft_section_details']
    params: DraftSectionDetailsParams


CADCommand = Union[
    ScanCommand, SaveAsCommand, MoveLayerCommand, MoveObjectCommand,
    ReplaceTextCommand, ReplaceBlockCommand, DeleteLayerCommand,
    CreateBoundaryCommand, CreateGridCommand, PlaceColumnsCommand,
    PlaceBeams2DCommand, LoadXiCADCommand, DetectXiCADCommand,
    RunXiCADCommand, XiCADWorkflowCommand, XicadSafeCommand,
    DraftSectionDetailsCommand,
]

COMMAND_MODELS = [
    ScanCommand, SaveAsCommand, MoveLayerCommand, MoveObjectCommand,
    ReplaceTextCommand, ReplaceBlockCommand, DeleteLayerCommand,
    CreateBoundaryCommand, CreateGridCommand, PlaceColumnsCommand,
    PlaceBeams2DCommand, LoadXiCADCommand, DetectXiCADCommand,
    RunXiCADCommand, XiCADWorkflowCommand, XicadSafeCommand,
    DraftSectionDetailsCommand,
]


def parse_command(data: dict[str, Any]) -> CADCommand:
    errors: list[str] = []
    for model in COMMAND_MODELS:
        try:
            return model.model_validate(data)
        except Exception as exc:
            errors.append(str(exc))
    raise ValueError('Unsupported or invalid command: ' + str(data.get('command')) + '\n' + '\n'.join(errors[:3]))


def load_command(path: str | Path) -> CADCommand:
    return parse_command(json.loads(Path(path).read_text(encoding='utf-8')))
