from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.table import Table

from src.adapters.xicad_adapter import XiCADAdapter
from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.ai.command_parser import load_command
from src.ai.command_validator import validate_allowed
from src.ai.safety_guard import prepare_safety
from src.app.logger import console, success, warn
from src.extensions.xicad_safe_bridge.executor import XicadSafeExecutor
from src.extensions.xicad_safe_bridge.json_io import load_safe_command
from src.extensions.xicad_safe_bridge.planner import XicadSafePlanner
from src.extensions.xicad_safe_bridge.registry import XicadAliasRegistry, default_xicad_registry
from src.integrations.xicad_command_catalog import filter_architecture_commands, parse_xicad_shortkey
from src.integrations.xicad_manifest import write_manifest
from src.integrations.xicad_paths import detect_xicad_profile
from src.integrations.xicad_workflows import get_workflow, list_workflows
from src.modifiers.architectural_modifier import (
    create_boundary,
    create_grid,
    execute_planned_actions,
    generate_architecture_summary,
    place_beams_2d,
    place_columns,
)
from src.reports.json_exporter import export_json
from src.reports.quantity_report import block_quantity
from src.reports.architecture_report import write_architecture_report
from src.reports.debug_bundle import collect_debug_bundle
from src.semantics.layer_taxonomy import layer_rules_as_rows
from src.semantics.object_classifier import classify_objects, summarize_semantics
from src.semantics.screen_capture import analyze_screen_image, capture_screen
from src.testing.environment_check import run_environment_check, write_environment_check
from src.scanners.block_scanner import block_summary
from src.scanners.layer_scanner import layer_counts
from src.scanners.text_scanner import extract_texts

app = typer.Typer(help='ZWCAD AI Architectural Modifier CLI')


def get_adapter(dwg: Optional[str] = None) -> ZWCADCOMAdapter:
    adapter = ZWCADCOMAdapter(visible=True)
    adapter.connect()
    if dwg:
        adapter.open_document(dwg)
    else:
        # If no DWG path provided, try to use the active document
        try:
            adapter.get_active_document()
        except Exception:
            # If no active document, it's okay for now, but commands might fail later
            pass
    return adapter


def _default_shortkey(xicad_root: str | None) -> Path | None:
    if not xicad_root:
        return None
    path = Path(xicad_root) / 'Lisp' / 'xiShortkey_origin.key'
    return path if path.exists() else None


def _load_objects_json(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(data, dict):
        if isinstance(data.get('objects'), list):
            return data['objects']
        if isinstance(data.get('items'), list):
            return data['items']
    if not isinstance(data, list):
        raise typer.BadParameter('input JSON must be a list or contain an objects/items list')
    return data


def _parse_bbox(value: str | None) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    parts = [int(part.strip()) for part in value.split(',')]
    if len(parts) != 4:
        raise typer.BadParameter('--bbox must be "left,top,width,height"')
    return tuple(parts)  # type: ignore[return-value]


def _semantic_summary_markdown(summary: dict) -> str:
    lines = [
        '# Object Semantic Summary',
        '',
        f"- Total objects: {summary.get('total_objects', summary.get('object_count', 0))}",
        f"- Classified objects: {summary.get('classified_objects', 0)}",
        f"- Unknown objects: {summary.get('unknown_objects', 0)}",
        f"- Color mismatch count: {summary.get('color_mismatch_count', 0)}",
        f"- Low confidence count: {summary.get('low_confidence_count', 0)}",
        '',
        '## By Semantic Type',
    ]
    for key, value in sorted(summary.get('by_semantic_type', {}).items()):
        lines.append(f'- {key}: {value}')
    return '\n'.join(lines) + '\n'


@app.command()
def connect():
    adapter = get_adapter()
    success('ZWCAD COM connection OK')
    adapter.close()


@app.command('env-check')
def env_check(
    dwg: str | None = typer.Option(None, help='Optional sample DWG path'),
    xicad_root: str | None = typer.Option(None, help='Optional XiCAD root path'),
    version: str | None = typer.Option(None, help='Preferred ZWCAD version: 2025 or 2026'),
    start_zwcad: bool = typer.Option(False, help='Allow COM CreateObject to start ZWCAD'),
    out_dir: str = typer.Option('outputs/zwcad_env_check', help='Output directory'),
):
    """Check Python packages, paths and ZWCAD 2025/2026 COM availability."""
    payload = run_environment_check(dwg=dwg, xicad_root=xicad_root, version=version, start_zwcad=start_zwcad)
    paths = write_environment_check(payload, out_dir)
    console.print({
        'zwcad_com_connected': payload.get('zwcad_com_connected'),
        'active_progid': payload.get('zwcad_active_progid'),
        'connection_mode': payload.get('zwcad_connection_mode'),
        'outputs': paths,
    })


@app.command()
def scan(dwg: Optional[str] = typer.Option(None, help='DWG file path (defaults to active document)'), out: str = typer.Option('outputs/objects.json', help='Output JSON path')):
    adapter = get_adapter(dwg)
    objects = adapter.scan_modelspace()
    export_json(objects, out)
    success(f'Scanned {len(objects)} objects -> {out}')


@app.command('list-layers')
def list_layers_cmd(dwg: Optional[str] = typer.Option(None, help='DWG file path (defaults to active document)')):
    adapter = get_adapter(dwg)
    layers = adapter.list_layers()
    table = Table('Layer')
    for layer in layers:
        table.add_row(layer)
    console.print(table)
    success(f'Found {len(layers)} layers')


@app.command()
def layers(dwg: Optional[str] = typer.Option(None, help='DWG file path (defaults to active document)')):
    adapter = get_adapter(dwg)
    counts = layer_counts(adapter.scan_modelspace())
    table = Table('Layer', 'Count')
    for key, value in counts.items():
        table.add_row(key, str(value))
    console.print(table)


@app.command()
def blocks(dwg: Optional[str] = typer.Option(None, help='DWG file path (defaults to active document)')):
    adapter = get_adapter(dwg)
    summary = block_summary(adapter.scan_modelspace())
    table = Table('Block', 'Count')
    for key, value in summary.items():
        table.add_row(key, str(value['count']))
    console.print(table)


@app.command()
def texts(dwg: Optional[str] = typer.Option(None, help='DWG file path (defaults to active document)'), out: str | None = typer.Option(None, help='Optional JSON output path')):
    adapter = get_adapter(dwg)
    rows = extract_texts(adapter.scan_modelspace())
    if out:
        export_json(rows, out)
        success(f'Exported {len(rows)} texts -> {out}')
    else:
        table = Table('Handle', 'Layer', 'Text')
        for row in rows[:200]:
            table.add_row(str(row.get('handle')), str(row.get('layer')), str(row.get('text')))
        console.print(table)


@app.command('analyze-architecture')
def analyze_architecture(dwg: str = typer.Option(..., help='DWG file path'), out_dir: str = typer.Option('outputs/architecture_report', help='Report output directory')):
    """Create architecture-focused JSON/Markdown/Excel audit outputs from a DWG scan."""
    adapter = get_adapter(dwg)
    objects = adapter.scan_modelspace()
    paths = write_architecture_report(objects, out_dir)
    success(f'Architecture report written: {out_dir} ({len(paths)} files)')


@app.command('collect-debug')
def collect_debug(
    dwg: str | None = typer.Option(None, help='Optional DWG file path'),
    xicad_root: str | None = typer.Option(None, help='Optional XiCAD root path'),
    out_dir: str = typer.Option('outputs/debug_bundle', help='Debug bundle output directory'),
    max_objects: int = typer.Option(200, help='Maximum object samples to include'),
):
    """Collect environment, optional ZWCAD scan and XiCAD detection information for support."""
    adapter = None
    if dwg:
        try:
            adapter = get_adapter(dwg)
        except Exception as exc:
            warn(f'ZWCAD connection failed; collecting environment only: {exc}')
    paths = collect_debug_bundle(adapter, dwg, xicad_root, out_dir, max_objects=max_objects)
    success(f'Debug bundle written: {out_dir} ({len(paths)} files)')


@app.command('classify-objects')
def classify_objects_cmd(
    dwg: str | None = typer.Option(None, help='DWG file path. Uses ZWCAD COM.'),
    input_json: str | None = typer.Option(None, help='Existing objects.json path. Works without ZWCAD.'),
    out: str = typer.Option('outputs/object_semantics.json', help='Object semantic JSON output path'),
    summary_out: str = typer.Option('outputs/object_semantic_summary.json', help='Semantic summary JSON output path'),
    format: str = typer.Option('json', help='Output format hint: json, xlsx, or md'),
    include_unknown: bool = typer.Option(True, help='Include unknown classifications'),
    confidence_threshold: float = typer.Option(0.0, help='Minimum confidence to include in the main output'),
    taxonomy: str | None = typer.Option(None, help='Optional taxonomy path; current built-in taxonomy is used.'),
):
    """Classify existing CAD objects by user-defined architectural layer rules plus geometry hints."""
    if taxonomy:
        warn('Custom taxonomy path is accepted for workflow compatibility; built-in taxonomy is used in this build.')
    if input_json:
        objects = _load_objects_json(input_json)
    elif dwg:
        adapter = get_adapter(dwg)
        objects = adapter.scan_modelspace()
    else:
        raise typer.BadParameter('Provide either --dwg or --input-json.')
    rows = classify_objects(objects)
    if not include_unknown:
        rows = [row for row in rows if row.get('semantic_type') != 'unknown' and row.get('category') != 'unknown']
    if confidence_threshold > 0:
        rows = [row for row in rows if float(row.get('confidence') or 0) >= confidence_threshold]
    summary = summarize_semantics(rows)
    export_json(rows, out)
    export_json(summary, summary_out)
    if format == 'xlsx':
        try:
            import pandas as pd  # type: ignore
            xlsx = str(Path(out).with_suffix('.xlsx'))
            pd.DataFrame(rows).to_excel(xlsx, index=False)
            success(f'Object semantics Excel -> {xlsx}')
        except Exception as exc:
            warn(f'Excel export skipped: {exc}')
    elif format == 'md':
        md = Path(out).with_suffix('.md')
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(_semantic_summary_markdown(summary), encoding='utf-8')
    table = Table('Semantic Type', 'Count')
    for key, value in sorted(summary.get('by_semantic_type', summary.get('by_category', {})).items()):
        table.add_row(key, str(value))
    console.print(table)
    success(f'Object semantics -> {out}')


@app.command('layer-taxonomy')
def layer_taxonomy(out: str | None = typer.Option(None, help='Optional JSON output path')):
    """Print the architectural layer taxonomy used for object classification."""
    rows = layer_rules_as_rows()
    if out:
        export_json(rows, out)
        success(f'Layer taxonomy written: {out}')
        return
    table = Table('Layer', 'Category', 'Role', 'Color', 'Description')
    for row in rows:
        table.add_row(str(row['layer']), str(row['category']), str(row['role']), str(row.get('color_index')), str(row['description']))
    console.print(table)


@app.command('capture-screen')
def capture_screen_cmd(
    out: str = typer.Option('outputs/screen_capture.png', help='Screenshot output path'),
    bbox: str | None = typer.Option(None, help='Optional capture box: left,top,width,height'),
    analyze: bool = typer.Option(True, help='Also run lightweight image analysis'),
):
    """Capture the visible screen as a fallback aid when CAD object access is insufficient."""
    result = capture_screen(out, region=_parse_bbox(bbox))
    payload = {'capture': result.__dict__}
    if result.ok and analyze and result.path:
        payload['image_analysis'] = analyze_screen_image(result.path)
    console.print(payload)
    if result.ok:
        success(f'Screen captured: {result.path}')
    else:
        warn(result.warning or 'Screen capture failed')


@app.command('xicad-profile')
def xicad_profile(xicad_root: str = typer.Option(..., help='XiCAD root path')):
    profile = detect_xicad_profile(xicad_root)
    console.print(profile.to_dict())


@app.command('detect-xicad')
def detect_xicad(xicad_root: str = typer.Option(..., help='XiCAD root path')):
    profile = detect_xicad_profile(xicad_root)
    console.print(profile.to_dict())


@app.command('xicad-manifest')
def xicad_manifest(xicad_root: str = typer.Option(..., help='XiCAD root path'), out: str = typer.Option('generated/xicad/xicad_file_manifest.json', help='Manifest output path'), hashes: bool = typer.Option(False, help='Include file hashes')):
    path = write_manifest(xicad_root, out, include_hashes=hashes)
    success(f'XiCAD manifest written: {path}')


@app.command('xicad-catalog')
def xicad_catalog(xicad_root: str | None = None, shortkey: str | None = None):
    key = Path(shortkey) if shortkey else _default_shortkey(xicad_root)
    if key is None:
        warn('No XiCAD shortkey file found. Showing built-in safe catalog aliases instead.')
        xicad_safe_catalog(None)
        return
    commands = filter_architecture_commands(parse_xicad_shortkey(key))
    table = Table('Alias', 'Function', 'Description', 'Section')
    for cmd in commands:
        table.add_row(cmd.alias, cmd.function, cmd.description, cmd.section)
    console.print(table)


@app.command('build-xicad-catalog')
def build_xicad_catalog(xicad_root: str = typer.Option(..., help='XiCAD root path'), out: str = typer.Option('generated/xicad/xicad_catalog.json', help='Catalog output path')):
    key = _default_shortkey(xicad_root)
    if key is None:
        rows = [item.model_dump(mode='json') for item in default_xicad_registry().list()]
        export_json(rows, out)
        success(f'Built-in XiCAD safe catalog written: {out}')
        return
    rows = [cmd.__dict__ for cmd in filter_architecture_commands(parse_xicad_shortkey(key))]
    export_json(rows, out)
    success(f'XiCAD catalog written: {out}')


@app.command('xicad-workflows')
def xicad_workflows():
    table = Table('Workflow', 'XiCAD Alias', 'Description')
    for wf in list_workflows():
        table.add_row(wf['name'], wf['alias'], wf['description'])
    console.print(table)


@app.command('load-xicad')
def load_xicad(dwg: str = typer.Option(..., help='DWG file path'), xicad_root: str = typer.Option(..., help='XiCAD root path')):
    adapter = get_adapter(dwg)
    loader = XiCADAdapter(adapter, xicad_root).load()
    success(f'XiCAD loader: {loader}')


@app.command('run-xicad')
def run_xicad(dwg: str = typer.Option(..., help='DWG file path'), alias: str = typer.Option(..., help='XiCAD alias'), xicad_root: str | None = typer.Option(None, help='XiCAD root path'), load_first: bool = typer.Option(False, help='Load XiCAD before running alias')):
    adapter = get_adapter(dwg)
    xi = XiCADAdapter(adapter, xicad_root or '.')
    if load_first and xicad_root:
        xi.load()
    xi.run_alias(alias)
    success(f'XiCAD command queued: {alias}')


def _planned_actions_for(cmd) -> list[dict] | None:
    if cmd.command == 'create_boundary':
        return create_boundary(**cmd.params.model_dump())
    if cmd.command == 'create_grid':
        return create_grid(**cmd.params.model_dump())
    if cmd.command == 'place_columns':
        return place_columns(**cmd.params.model_dump())
    if cmd.command == 'place_beams_2d':
        return place_beams_2d(**cmd.params.model_dump())
    return None


@app.command('run-command')
def run_command(
    dwg: str = typer.Option(..., help='DWG file path'),
    command: str = typer.Option(..., help='Command JSON path'),
    dry_run: bool = typer.Option(True, help='Preview only'),
    execute: bool = typer.Option(False, help='Actually execute'),
    save_as: str | None = typer.Option(None, help='Save modified DWG as'),
    yes: bool = typer.Option(False, help='Required for delete commands when executing'),
):
    """Validate and run a JSON command.

    Dry-run does not require ZWCAD/COM. This is important for Codex, CI and
    non-Windows review environments. The adapter is opened only when a command
    is actually executed.
    """
    cmd = load_command(command)
    validate_allowed(cmd)
    will_execute = bool(execute and not dry_run)
    mutating = cmd.command in {
        'move_layer','move_object_by_handle','replace_text','replace_block',
        'delete_layer_objects','create_boundary','create_grid','place_columns',
        'place_beams_2d','load_xicad','run_xicad_command','xicad_workflow',
        'run_xicad_workflow','xicad_safe_execute'
    }
    if will_execute and mutating and not save_as:
        raise typer.BadParameter('--save-as is required for mutating --execute commands.')
    if will_execute and cmd.command == 'delete_layer_objects' and not (getattr(cmd.params, 'yes', False) or yes):
        raise typer.BadParameter('delete_layer_objects requires --yes when executing.')
    safety = prepare_safety(cmd, dwg, will_execute)
    warn(f'Safety: {safety}')
    result = {'command': cmd.command, 'executed': will_execute, 'result': None}

    if cmd.command in {'xicad_safe_plan', 'xicad_safe_execute'} and not will_execute:
        safe_command = cmd.model_copy(update={'dry_run': True})
        xicad_root = safe_command.params.get('xicad_root') if hasattr(safe_command.params, 'get') else None
        registry = _safe_bridge_registry(xicad_root)
        plan = XicadSafeExecutor(XicadSafePlanner(registry)).preview(safe_command)
        result['result'] = {'safe_bridge_plan': plan.model_dump(mode='json')}
        console.print(result)
        return

    if not will_execute:
        result['result'] = {'preview': cmd.model_dump()}
        actions = _planned_actions_for(cmd)
        if actions is not None:
            result['planned_actions'] = actions
        elif cmd.command in {'xicad_workflow', 'run_xicad_workflow'}:
            wf = get_workflow(cmd.params.workflow)
            result['planned_actions'] = [{'action': 'run_xicad_command', 'alias': wf['alias'], 'description': wf['description'], 'interactive': True}]
        elif cmd.command == 'run_xicad_command':
            result['planned_actions'] = [{'action': 'run_xicad_command', 'alias': cmd.params.alias, 'args': cmd.params.args, 'interactive': cmd.params.interactive}]
        elif cmd.command == 'load_xicad':
            result['planned_actions'] = [{'action': 'load_xicad', 'xicad_root': cmd.params.xicad_root}]
        elif cmd.command == 'detect_xicad':
            result['profile'] = detect_xicad_profile(cmd.params.xicad_root).to_dict()
        elif cmd.command == 'build_xicad_catalog':
            key = _default_shortkey(cmd.params.xicad_root)
            result['catalog_source'] = str(key) if key else None
        console.print(result)
        return

    adapter = get_adapter(dwg)
    objects_before = adapter.scan_modelspace()

    if cmd.command in {'xicad_safe_plan', 'xicad_safe_execute'}:
        safe_command = cmd.model_copy(update={'dry_run': cmd.command != 'xicad_safe_execute'})
        xicad_root = safe_command.params.get('xicad_root') if hasattr(safe_command.params, 'get') else None
        registry = _safe_bridge_registry(xicad_root)
        plan = XicadSafeExecutor(XicadSafePlanner(registry)).execute(safe_command, adapter)
        result['result'] = {'safe_bridge_plan': plan.model_dump(mode='json')}
    elif cmd.command == 'move_layer':
        p = cmd.params
        result['result'] = {'moved': adapter.move_layer(p.layer, p.dx, p.dy, p.dz)}
    elif cmd.command == 'move_object_by_handle':
        p = cmd.params
        result['result'] = {'moved': adapter.move_entity(p.handle, p.dx, p.dy, p.dz)}
    elif cmd.command == 'replace_text':
        p = cmd.params
        result['result'] = {'changed': adapter.replace_text(p.find, p.replace, p.layer)}
    elif cmd.command == 'replace_block':
        p = cmd.params
        result['result'] = adapter.replace_block(p.target_block, p.new_block, p.layer, p.preserve_rotation, p.preserve_scale, p.preserve_layer, p.delete_original)
    elif cmd.command == 'delete_layer_objects':
        result['result'] = {'deleted': adapter.delete_layer_objects(cmd.params.layer, yes=bool(cmd.params.yes or yes), dry_run=False)}
    elif cmd.command == 'save_as':
        adapter.save_as(cmd.params.path)
        result['result'] = {'saved_as': cmd.params.path}
    elif cmd.command == 'load_xicad':
        result['result'] = {'loader': str(XiCADAdapter(adapter, cmd.params.xicad_root).load())}
    elif cmd.command == 'run_xicad_command':
        p = cmd.params
        xi = XiCADAdapter(adapter, p.xicad_root or '.')
        xi.run_alias(p.alias) if p.interactive else xi.run_scripted_alias(p.alias, p.args)
        result['result'] = {'queued': p.alias, 'interactive': p.interactive}
    elif cmd.command in {'xicad_workflow', 'run_xicad_workflow'}:
        wf = get_workflow(cmd.params.workflow)
        XiCADAdapter(adapter, cmd.params.xicad_root or '.').run_alias(wf['alias'])
        result['result'] = {'workflow': cmd.params.workflow, 'queued_alias': wf['alias']}
    elif cmd.command in {'create_boundary','create_grid','place_columns','place_beams_2d'}:
        actions = _planned_actions_for(cmd) or []
        result['result'] = execute_planned_actions(adapter, actions)
    else:
        result['result'] = {'status': 'no_mutation_needed'}

    if save_as:
        adapter.save_as(save_as)
        result['saved_as'] = save_as
    objects_after = adapter.scan_modelspace()
    result['summary'] = {'before_count': len(objects_before), 'after_count': len(objects_after)}
    console.print(result)


@app.command('quantity')
def quantity(dwg: str = typer.Option(..., help='DWG file path'), out: str = typer.Option('outputs/quantity.json', help='Output path')):
    adapter = get_adapter(dwg)
    rows = block_quantity(adapter.scan_modelspace())
    export_json(rows, out)
    success(f'Quantity report -> {out}')


# ---------------------------------------------------------------------------
# XiCAD Safe Bridge commands
# ---------------------------------------------------------------------------

def _safe_bridge_registry(xicad_root: str | None = None) -> XicadAliasRegistry:
    if xicad_root:
        key_path = Path(xicad_root) / 'Lisp' / 'xiShortkey_origin.key'
        return XicadAliasRegistry.from_key_file(key_path)
    return default_xicad_registry()


@app.command('xicad-safe-catalog')
def xicad_safe_catalog(xicad_root: str | None = None):
    registry = _safe_bridge_registry(xicad_root)
    table = Table('Alias', 'Name', 'Category', 'Risk', 'Interactive')
    for item in registry.list():
        table.add_row(item.alias, item.name, item.category.value, item.risk.value, str(item.interactive_required))
    console.print(table)


@app.command('xicad-safe-plan')
def xicad_safe_plan(
    command_arg: str | None = typer.Argument(None, help='XiCAD safe JSON command'),
    command: str | None = typer.Option(None, help='XiCAD safe JSON command'),
    xicad_root: str | None = typer.Option(None, help='XiCAD root path'),
    out: str | None = typer.Option(None, help='Optional output JSON path'),
):
    command_path = command or command_arg
    if not command_path:
        raise typer.BadParameter('Provide a command JSON path as an argument or --command.')
    safe_command = load_safe_command(command_path)
    registry = _safe_bridge_registry(xicad_root)
    plan = XicadSafePlanner(registry).build_plan(safe_command)
    payload = plan.model_dump(mode='json')
    if out:
        export_json(payload, out)
        success(f'XiCAD safe plan written: {out}')
    else:
        console.print(payload)


@app.command('xicad-safe-run')
def xicad_safe_run(
    dwg: str = typer.Option(..., help='DWG file path'),
    command: str = typer.Option(..., help='XiCAD safe JSON command'),
    xicad_root: str | None = typer.Option(None, help='XiCAD root path'),
    execute: bool = typer.Option(False, help='Actually execute'),
    load_first: bool = typer.Option(True, help='Load XiCAD before command'),
    save_as: str | None = typer.Option(None, help='Save modified DWG as'),
):
    safe_command = load_safe_command(command)
    safe_command.load_first = load_first
    if execute:
        if not save_as:
            raise typer.BadParameter('--save-as is required with --execute.')
        safe_command.dry_run = False
    registry = _safe_bridge_registry(xicad_root)
    executor = XicadSafeExecutor(XicadSafePlanner(registry))
    adapter = get_adapter(dwg)
    if safe_command.load_first and xicad_root:
        XiCADAdapter(adapter, xicad_root).load()
    plan = executor.execute(safe_command, adapter)
    console.print(plan.model_dump(mode='json'))
    if save_as and plan.can_execute:
        adapter.save_as(save_as)
        success(f'Saved modified DWG: {save_as}')
