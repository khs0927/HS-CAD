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
from src.integrations.xicad_symbol_staging import (
    analyze_xicad_symbol_system,
    build_master_symbol_review_table,
    build_xicad_symbol_staging,
    configure_xicad_block_library_default,
    export_all_drawing_blocks_to_xicad,
    export_dxf_block_symbols,
    mirror_hscad_library_to_xicad_native_folders,
)
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
from src.scanners.dxf_indexer import convert_dwg_to_dxf, index_dxf_to_sqlite, query_index as query_sqlite_index
from src.scanners.layer_scanner import layer_counts
from src.scanners.native_audit import run_native_audit
from src.scanners.native_fast_scan import fast_scan_active
from src.scanners.scan_strategy import recommend_scan_strategy
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
def scan(
    dwg: str = typer.Option(..., help='DWG file path'),
    out: str = typer.Option('outputs/objects.json', help='Output JSON path'),
    mode: str = typer.Option('minimal', help='Scan mode: minimal, index, or full'),
    confirm_heavy: bool = typer.Option(False, help='Allow explicit heavy full COM scans on large drawings'),
):
    adapter = get_adapter(dwg)
    objects = adapter.scan_modelspace(mode=mode, confirm_heavy=confirm_heavy)
    export_json(objects, out)
    success(f'Scanned {len(objects)} objects in {mode} mode -> {out}')


@app.command('fast-scan')
def fast_scan(active: bool = typer.Option(False, help='Use the active ZWCAD document'), out: str = typer.Option('generated/fast_scan_report.json', help='Output JSON path')):
    if not active:
        raise typer.BadParameter('fast-scan currently requires --active')
    adapter = get_adapter()
    payload = fast_scan_active(adapter)
    export_json(payload, out)
    success(f'Fast scan written: {out}')


@app.command('audit-native')
def audit_native(active: bool = typer.Option(False, help='Use the active ZWCAD document'), out: str = typer.Option('generated/native_audit.json', help='Output JSON path')):
    if not active:
        raise typer.BadParameter('audit-native currently requires --active')
    adapter = get_adapter()
    payload = run_native_audit(adapter, out)
    export_json(payload, out)
    success(f'Native audit written: {out}')


@app.command('index-dxf')
def index_dxf(
    dwg: str = typer.Option(..., help='DWG or DXF path'),
    out: str = typer.Option('generated/index.sqlite', help='SQLite index path'),
    oda_converter: str | None = typer.Option(None, help='Optional ODA File Converter executable path for DWG input'),
):
    source = Path(dwg)
    dxf = source
    if source.suffix.lower() == '.dwg':
        dxf = convert_dwg_to_dxf(source, Path(out).with_suffix('') / 'dxf', oda_converter)
    payload = index_dxf_to_sqlite(dxf, Path(out))
    export_json(payload, Path(out).with_suffix('.json'))
    success(f'DXF index written: {out}')


@app.command('query-index')
def query_index(index: str = typer.Option('generated/index.sqlite', help='SQLite index path'), where: str = typer.Option(..., help='SQL WHERE expression'), limit: int = typer.Option(200, help='Maximum rows')):
    rows = query_sqlite_index(Path(index), where, limit)
    console.print(rows)


@app.command('scan-layer')
def scan_layer(
    layer: str = typer.Option(..., help='Layer name'),
    active: bool = typer.Option(False, help='Use active document'),
    dwg: str | None = typer.Option(None, help='Optional DWG path'),
    types: str = typer.Option('', help='Comma-separated entity types'),
    detail: str = typer.Option('minimal', help='minimal or index'),
    out: str | None = typer.Option(None, help='Optional JSON output path'),
):
    if not active and not dwg:
        raise typer.BadParameter('Provide --active or --dwg')
    adapter = get_adapter(None if active else dwg)
    wanted = {t.strip().upper() for t in types.split(',') if t.strip()}
    rows = [
        item for item in adapter.scan_modelspace(mode=detail)
        if str(item.get('layer')) == layer and (not wanted or str(item.get('entity_type')).upper() in wanted)
    ]
    if out:
        export_json(rows, out)
        success(f'Scanned {len(rows)} layer objects -> {out}')
    else:
        console.print(rows[:200])


@app.command('scan-window')
def scan_window(
    bbox: str = typer.Option(..., help='xmin,ymin,xmax,ymax'),
    active: bool = typer.Option(False, help='Use active document'),
    dwg: str | None = typer.Option(None, help='Optional DWG path'),
    types: str = typer.Option('', help='Comma-separated entity types'),
    out: str | None = typer.Option(None, help='Optional JSON output path'),
):
    if not active and not dwg:
        raise typer.BadParameter('Provide --active or --dwg')
    xmin, ymin, xmax, ymax = [float(p.strip()) for p in bbox.split(',')]
    adapter = get_adapter(None if active else dwg)
    wanted = {t.strip().upper() for t in types.split(',') if t.strip()}
    rows = []
    for item in adapter.scan_modelspace(mode='index'):
        if wanted and str(item.get('entity_type')).upper() not in wanted:
            continue
        ibox = item.get('bbox')
        if not ibox:
            continue
        if ibox[2] >= xmin and ibox[0] <= xmax and ibox[3] >= ymin and ibox[1] <= ymax:
            rows.append(item)
    if out:
        export_json(rows, out)
        success(f'Scanned {len(rows)} window objects -> {out}')
    else:
        console.print(rows[:200])


@app.command('scan-selection')
def scan_selection(active: bool = typer.Option(False, help='Use active document'), out: str = typer.Option('generated/selection.json', help='Output JSON path')):
    if not active:
        raise typer.BadParameter('scan-selection currently requires --active')
    adapter = get_adapter()
    doc = adapter.get_active_document()
    rows = []
    for i in range(doc.SelectionSets.Count):
        ss = doc.SelectionSets.Item(i)
        for j in range(ss.Count):
            rows.append(adapter._entity_to_dict_index(ss.Item(j)))
    export_json(rows, out)
    success(f'Selection scan written: {out}')


@app.command('scan-strategy')
def scan_strategy(total_objects: int = typer.Option(..., help='Object count'), requested_detail: str = typer.Option('minimal', help='minimal, index, or full')):
    strategy = recommend_scan_strategy(total_objects, requested_detail)
    console.print(strategy.__dict__)


@app.command()
def layers(dwg: str = typer.Option(..., help='DWG file path')):
    adapter = get_adapter(dwg)
    counts = layer_counts(adapter.scan_modelspace(mode='minimal'))
    table = Table('Layer', 'Count')
    for key, value in counts.items():
        table.add_row(key, str(value))
    console.print(table)


@app.command()
def blocks(dwg: str = typer.Option(..., help='DWG file path')):
    adapter = get_adapter(dwg)
    summary = block_summary(adapter.scan_modelspace(mode='index'))
    table = Table('Block', 'Count')
    for key, value in summary.items():
        table.add_row(key, str(value['count']))
    console.print(table)


@app.command()
def texts(dwg: str = typer.Option(..., help='DWG file path'), out: str | None = typer.Option(None, help='Optional JSON output path')):
    adapter = get_adapter(dwg)
    rows = extract_texts(adapter.scan_modelspace(mode='index'))
    if out:
        export_json(rows, out)
        success(f'Exported {len(rows)} texts -> {out}')
    else:
        table = Table('Handle', 'Layer', 'Text')
        for row in rows[:200]:
            table.add_row(str(row.get('handle')), str(row.get('layer')), str(row.get('text')))
        console.print(table)


@app.command('analyze-architecture')
def analyze_architecture(
    dwg: str = typer.Option(..., help='DWG file path'),
    out_dir: str = typer.Option('outputs/architecture_report', help='Report output directory'),
    mode: str = typer.Option('index', help='Scan mode for the report'),
    confirm_heavy: bool = typer.Option(False, help='Allow full scan on large drawings'),
):
    """Create architecture-focused JSON/Markdown audit outputs from a DWG scan."""
    adapter = get_adapter(dwg)
    objects = adapter.scan_modelspace(mode=mode, confirm_heavy=confirm_heavy)
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


@app.command('build-xicad-symbol-staging')
def build_xicad_symbol_staging_cli(
    observed_report: str = typer.Option('generated/fast_scan_report.json', help='fast-scan report containing user_blocks_observed'),
    xicad_root: str = typer.Option('C:/xicad', help='XiCAD root path'),
    out_dir: str = typer.Option('generated/xicad_symbols_staging', help='Staging output directory'),
    target_subdir: str = typer.Option('HS-CAD', help='Subfolder name below XiCAD xiLib/심볼'),
    dxf_source: list[str] = typer.Option([], help='Optional DXF files used for block shape inference'),
    copy_matches: bool = typer.Option(True, help='Copy matched existing XiCAD DWG/SLD files into staging'),
):
    payload = build_xicad_symbol_staging(
        observed_report=observed_report,
        dxf_sources=dxf_source,
        xicad_root=xicad_root,
        out_dir=out_dir,
        target_subdir=target_subdir,
        copy_matches=copy_matches,
    )
    counts = payload["counts"]
    success(
        f'XiCAD symbol staging written: {out_dir} '
        f'({counts["total"]} candidates, {counts["by_source_status"]})'
    )


@app.command('export-xicad-symbol-dxf')
def export_xicad_symbol_dxf_cli(
    dxf_source: list[str] = typer.Option(..., help='DXF files used as block-definition sources'),
    catalog: str = typer.Option('generated/xicad_symbols_staging/hs_cad_symbol_catalog.json', help='Symbol catalog path'),
    out_dir: str = typer.Option('generated/xicad_symbols_staging/exported_dxf', help='Output directory for per-symbol DXF files'),
    category: list[str] = typer.Option([], help='Optional categories to export'),
    convert_to_dwg: bool = typer.Option(False, help='Convert exported DXFs to DWG with ODA File Converter'),
    oda_converter: str | None = typer.Option(None, help='Optional ODAFileConverter.exe path'),
):
    payload = export_dxf_block_symbols(
        dxf_sources=dxf_source,
        catalog_path=catalog,
        out_dir=out_dir,
        categories=category,
        convert_to_dwg=convert_to_dwg,
        oda_converter=oda_converter,
    )
    success(f'Exported {payload["exported_count"]} DXF symbol files -> {out_dir}')


@app.command('analyze-xicad-symbol-system')
def analyze_xicad_symbol_system_cli(
    xicad_root: str = typer.Option('C:/xicad', help='XiCAD root path'),
    out: str = typer.Option('generated/xicad_symbols_staging/xicad_symbol_system_analysis.json', help='Analysis JSON path'),
):
    payload = analyze_xicad_symbol_system(xicad_root=xicad_root, out_path=out)
    totals = payload["totals"]
    success(
        f'XiCAD symbol system analyzed: {out} '
        f'(xiLib DWG {totals["xiLib_dwg"]}, Lib DWG {totals["Lib_dwg"]})'
    )


@app.command('export-all-drawing-blocks-to-xicad')
def export_all_drawing_blocks_to_xicad_cli(
    root: list[str] = typer.Option(['.'], help='Root files/folders to scan for DWG/DXF sources'),
    xicad_root: str = typer.Option('C:/xicad', help='XiCAD root path'),
    out_dir: str = typer.Option('generated/xicad_symbols_staging/all_drawings', help='Working output directory'),
    target_subdir: str = typer.Option('HS-CAD-ALL', help='Subfolder below XiCAD xiLib/심볼'),
    install: bool = typer.Option(False, help='Copy converted DWG symbols into XiCAD after export'),
    include_review_only: bool = typer.Option(False, help='Also install anonymous/review-only blocks'),
    oda_converter: str | None = typer.Option(None, help='Optional ODAFileConverter.exe path'),
):
    payload = export_all_drawing_blocks_to_xicad(
        roots=root,
        xicad_root=xicad_root,
        out_dir=out_dir,
        target_subdir=target_subdir,
        install=install,
        include_review_only=include_review_only,
        oda_converter=oda_converter,
    )
    success(
        f'All drawing blocks processed: {payload["catalog"]["counts"]["total"]} candidates, '
        f'{payload["export"]["exported_count"]} exported'
    )


@app.command('configure-xicad-block-library')
def configure_xicad_block_library_cli(
    xicad_root: str = typer.Option('C:/xicad', help='XiCAD root path'),
    default_folder: str = typer.Option(r'<MAINPATH>\심볼\HS-CAD-XICAD', help='Default xiBlkLibrary folder value'),
):
    payload = configure_xicad_block_library_default(xicad_root=xicad_root, default_folder=default_folder)
    success(f'XiCAD block library default updated: {payload["new_value"]} (backup: {payload["backup"]})')


@app.command('mirror-xicad-native-folders')
def mirror_xicad_native_folders_cli(
    source_subdir: str = typer.Option('HS-CAD-ALL', help='Source subfolder below XiCAD xiLib/심볼'),
    target_subdir: str = typer.Option('HS-CAD-XICAD', help='Target subfolder below XiCAD xiLib/심볼'),
    xicad_root: str = typer.Option('C:/xicad', help='XiCAD root path'),
    catalog: str = typer.Option('generated/xicad_symbols_staging/all_drawings/all_drawing_block_catalog.json', help='All drawing block catalog path'),
    analysis: str = typer.Option('generated/xicad_symbols_staging/xicad_symbol_system_analysis.json', help='XiCAD symbol system analysis path'),
    out: str = typer.Option('generated/xicad_symbols_staging/all_drawings/xicad_native_folder_mirror_report.json', help='Report JSON path'),
):
    payload = mirror_hscad_library_to_xicad_native_folders(
        source_subdir=source_subdir,
        target_subdir=target_subdir,
        xicad_root=xicad_root,
        catalog_path=catalog,
        analysis_path=analysis,
        out_path=out,
    )
    success(f'XiCAD-native mirror written: {payload["target_root"]} ({payload["copied_count"]} copied)')


@app.command('build-symbol-review-table')
def build_symbol_review_table_cli(
    xicad_root: str = typer.Option('C:/xicad', help='XiCAD root path'),
    out_dir: str = typer.Option('generated/xicad_symbols_staging', help='Output directory'),
    catalog: str = typer.Option('generated/xicad_symbols_staging/all_drawings/all_drawing_block_catalog.json', help='All drawing block catalog path'),
):
    reports = {
        'HS-CAD-ALL': 'generated/zwcad_symbol_live_test/hscad_all_full_library_insert_report.json',
        'HS-CAD-XICAD': 'generated/zwcad_symbol_live_test/hscad_xicad_native_full_insert_report.json',
        'HS-CAD-REVIEW': 'generated/zwcad_symbol_live_test/hscad_review_only_insert_report.json',
    }
    payload = build_master_symbol_review_table(
        xicad_root=xicad_root,
        catalog_path=catalog,
        validation_reports=reports,
        out_dir=out_dir,
    )
    success(f'Symbol review table written: {payload["csv"]} ({payload["rows"]} rows)')


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
    before_count = adapter._modelspace_count()

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
    after_count = adapter._modelspace_count()
    result['summary'] = {'before_count': before_count, 'after_count': after_count}
    console.print(result)


@app.command('quantity')
def quantity(dwg: str = typer.Option(..., help='DWG file path'), out: str = typer.Option('outputs/quantity.json', help='Output path')):
    adapter = get_adapter(dwg)
    rows = block_quantity(adapter.scan_modelspace(mode='index'))
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

