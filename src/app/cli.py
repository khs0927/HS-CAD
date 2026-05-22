from __future__ import annotations

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
    draft_section_details,
)
from src.reports.json_exporter import export_json
from src.reports.quantity_report import block_quantity
from src.scanners.block_scanner import block_summary
from src.scanners.layer_scanner import layer_counts
from src.scanners.text_scanner import extract_texts

app = typer.Typer(help='ZWCAD AI Architectural Modifier CLI')


def get_adapter(dwg: Optional[str] = None) -> ZWCADCOMAdapter:
    adapter = ZWCADCOMAdapter(visible=True)
    adapter.connect()
    if dwg:
        adapter.open_document(dwg)
    return adapter


def _default_shortkey(xicad_root: str | None) -> Path | None:
    if not xicad_root:
        return None
    path = Path(xicad_root) / 'Lisp' / 'xiShortkey_origin.key'
    return path if path.exists() else None


@app.command()
def connect():
    adapter = get_adapter()
    success('ZWCAD COM connection OK')
    adapter.close()


@app.command()
def scan(dwg: str = typer.Option(..., help='DWG file path'), out: str = typer.Option('outputs/objects.json', help='Output JSON path')):
    adapter = get_adapter(dwg)
    objects = adapter.scan_modelspace()
    export_json(objects, out)
    success(f'Scanned {len(objects)} objects -> {out}')


@app.command()
def layers(dwg: str = typer.Option(..., help='DWG file path')):
    adapter = get_adapter(dwg)
    counts = layer_counts(adapter.scan_modelspace())
    table = Table('Layer', 'Count')
    for key, value in counts.items():
        table.add_row(key, str(value))
    console.print(table)


@app.command()
def blocks(dwg: str = typer.Option(..., help='DWG file path')):
    adapter = get_adapter(dwg)
    summary = block_summary(adapter.scan_modelspace())
    table = Table('Block', 'Count')
    for key, value in summary.items():
        table.add_row(key, str(value['count']))
    console.print(table)


@app.command()
def texts(dwg: str = typer.Option(..., help='DWG file path'), out: str | None = typer.Option(None, help='Optional JSON output path')):
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
    """Create architecture-focused JSON/Markdown audit outputs from a DWG scan."""
    adapter = get_adapter(dwg)
    objects = adapter.scan_modelspace()
    summary = generate_architecture_summary(objects)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    export_json(objects, out / 'objects.json')
    export_json(summary, out / 'architecture_summary.json')
    md_lines = [
        '# Architecture Drawing Audit',
        '',
        f'- Object count: {summary["object_count"]}',
        '',
        '## Entity counts',
    ]
    for key, value in summary['entity_counts'].items():
        md_lines.append(f'- {key}: {value}')
    md_lines += ['', '## Architecture layer counts']
    for key, value in summary['architecture_layers']['architecture_layer_counts'].items():
        md_lines.append(f'- {key}: {value}')
    md_lines += ['', '## Polyline quality', f'- Closed: {summary["polyline_quality"]["closed_count"]}', f'- Open: {summary["polyline_quality"]["open_count"]}']
    (out / 'drawing_audit.md').write_text('\n'.join(md_lines), encoding='utf-8')
    success(f'Architecture report written: {out}')


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
        raise typer.BadParameter('Provide --shortkey or --xicad-root containing Lisp/xiShortkey_origin.key')
    commands = filter_architecture_commands(parse_xicad_shortkey(key))
    table = Table('Alias', 'Function', 'Description', 'Section')
    for cmd in commands:
        table.add_row(cmd.alias, cmd.function, cmd.description, cmd.section)
    console.print(table)


@app.command('build-xicad-catalog')
def build_xicad_catalog(xicad_root: str = typer.Option(..., help='XiCAD root path'), out: str = typer.Option('generated/xicad/xicad_catalog.json', help='Catalog output path')):
    key = _default_shortkey(xicad_root)
    if key is None:
        raise typer.BadParameter('No xiShortkey_origin.key found under xicad_root/Lisp')
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
    if cmd.command == 'draft_section_details':
        return draft_section_details(**cmd.params.model_dump())
    return None

@app.command('run-command')
def run_command(dwg: str = typer.Option(..., help='DWG file path'), command: str = typer.Option(..., help='Command JSON path'), dry_run: bool = typer.Option(False, help='Preview only'), execute: bool = typer.Option(False, help='Actually execute'), save_as: str | None = typer.Option(None, help='Save modified DWG as')):
    """Validate and run a JSON command.

    Dry-run does not require ZWCAD/COM. This is important for Codex, CI and
    non-Windows review environments. The adapter is opened only when a command
    is actually executed.
    """
    cmd = load_command(command)
    validate_allowed(cmd)
    will_execute = bool(execute and not dry_run)
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
        result['result'] = adapter.replace_block(p.target_block, p.new_block, p.layer)
    elif cmd.command == 'delete_layer_objects':
        result['result'] = {'deleted': adapter.delete_layer_objects(cmd.params.layer)}
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
    elif cmd.command in {'create_boundary','create_grid','place_columns','place_beams_2d','draft_section_details'}:
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
def xicad_safe_plan(command: str = typer.Option(..., help='XiCAD safe JSON command'), xicad_root: str | None = typer.Option(None, help='XiCAD root path'), out: str | None = typer.Option(None, help='Optional output JSON path')):
    safe_command = load_safe_command(command)
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


@app.command('floorplan-analyze')
def floorplan_analyze(
    image: Path = typer.Option(..., '--image', help='분석 대상 도면 이미지 경로 (PNG, JPG, BMP 등)'),
    out_dir: Path = typer.Option(Path('outputs/floorplan_out'), '--out-dir', help='DXF 및 레포트 출력 폴더'),
    dry_run: bool = typer.Option(True, '--dry-run/--production', help='Dry-run 모드 실행 여부 (기본값 True)'),
    vlm_refine: bool = typer.Option(True, '--vlm/--no-vlm', help='VLM 피드백 리뷰 실행 여부'),
):
    """Unified Floorplan-to-CAD 파이프라인을 실행합니다 (기본값 Dry-Run)."""
    from neuro_seq_cad.app.cli import analyze as ns_analyze
    # ZWCAD 수정 등은 절대 하지 않고, 순수 파일 변환 파이프라인 호출
    ns_analyze(image=image, output_dir=out_dir, dry_run=dry_run, vlm_refine=vlm_refine)

