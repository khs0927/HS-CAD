from __future__ import annotations

from src.ai.command_parser import CADCommand

ALLOWED_COMMANDS = {
    'scan_all','scan_layers','scan_blocks','scan_texts','export_objects_json',
    'move_layer','move_object_by_handle','replace_text','replace_block',
    'delete_layer_objects','create_boundary','create_grid','place_columns',
    'place_beams_2d','generate_quantity_report','save_as','load_xicad',
    'detect_xicad','build_xicad_catalog','run_xicad_command','xicad_workflow',
    'run_xicad_workflow','xicad_safe_plan','xicad_safe_execute','analyze_architecture'
}


def _require_non_empty(value: object, field: str) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f'Required value is empty: {field}')


def validate_allowed(command: CADCommand) -> None:
    if command.command not in ALLOWED_COMMANDS:
        raise ValueError(f'Command not allowed: {command.command}')
    params = getattr(command, 'params', None)
    if command.command in {'move_layer','delete_layer_objects'}:
        _require_non_empty(getattr(params, 'layer', None), 'layer')
    if command.command == 'move_object_by_handle':
        _require_non_empty(getattr(params, 'handle', None), 'handle')
    if command.command == 'replace_text':
        _require_non_empty(getattr(params, 'find', None), 'find')
    if command.command == 'replace_block':
        _require_non_empty(getattr(params, 'target_block', None), 'target_block')
        _require_non_empty(getattr(params, 'new_block', None), 'new_block')
    if command.command in {'run_xicad_command'}:
        _require_non_empty(getattr(params, 'alias', None), 'alias')
    if command.command in {'xicad_safe_plan','xicad_safe_execute'}:
        _require_non_empty(getattr(command, 'alias', None), 'alias')
