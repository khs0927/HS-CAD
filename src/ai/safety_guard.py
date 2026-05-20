from __future__ import annotations

from pathlib import Path
from typing import Any

from src.ai.command_parser import CADCommand
from src.utils.file_backup import backup_file

MUTATING_COMMANDS = {
    'move_layer','move_object_by_handle','replace_text','replace_block',
    'delete_layer_objects','create_boundary','create_grid','place_columns',
    'place_beams_2d','save_as','load_xicad','run_xicad_command',
    'xicad_workflow','run_xicad_workflow','xicad_safe_execute'
}
DELETE_COMMANDS = {'delete_layer_objects'}


def prepare_safety(command: CADCommand, dwg_path: str | None, execute: bool, backup_dir: str = 'backups') -> dict[str, Any]:
    report: dict[str, Any] = {'will_execute': execute, 'backup': None, 'warnings': []}
    if command.command in DELETE_COMMANDS:
        report['warnings'].append('Delete command requested. Review carefully before executing.')
    if command.command in MUTATING_COMMANDS and execute and getattr(command, 'safety', None) and command.safety.backup_required and dwg_path:
        report['backup'] = str(backup_file(Path(dwg_path), backup_dir))
    if getattr(command, 'safety', None) and command.safety.preview_required and not execute:
        report['warnings'].append('Preview/dry-run mode: no changes will be applied.')
    if execute and command.command in {'run_xicad_command','xicad_workflow','run_xicad_workflow','xicad_safe_execute'}:
        report['warnings'].append('XiCAD commands may be interactive inside ZWCAD. Confirm the command line workflow manually.')
    return report
