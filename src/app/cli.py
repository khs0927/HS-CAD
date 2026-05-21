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
from src.company_profile.hs_cad_profile_loader import build_company_drafting_profile, write_profile_to_file
import json
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


@app.command('corpus-scan')
def corpus_scan(
    root: str = typer.Option(..., help='Root folder containing drawing files'),
    out: str = typer.Option('outputs/corpus', help='Output directory for the manifest'),
) -> None:
    """Discover files under *root* and write a manifest JSON.

    The command creates a ``manifest.json`` inside *out* that lists the
    discovered files with basic metadata.
    """
    from src.corpus.file_discovery import discover_files, file_metadata
    from src.corpus.manifest import Manifest
    from src.corpus.models import CorpusFile
    root_path = Path(root)
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / 'manifest.json'
    manifest = Manifest.load(manifest_path)
    for file_path in discover_files(root_path):
        meta = file_metadata(root_path, file_path)
        # Convert to Pydantic model for validation (optional)
        try:
            CorpusFile(**meta)
        except Exception:
            continue
        manifest.add_or_update(meta)
    manifest.dump(manifest_path)
    success(f'Manifest written: {manifest_path}')


@app.command('corpus-index')
def corpus_index(
    manifest: str = typer.Option(..., help='Path to manifest.json'),
    out: str = typer.Option('outputs/corpus', help='Output directory for the index'),
    limit: int = typer.Option(None, help='Maximum number of files to process'),
) -> None:
    """Index files listed in *manifest* and create a SQLite knowledge store.

    The command writes ``cad_knowledge.sqlite`` and per‑file JSON records to
    *out*.
    """
    from src.corpus.corpus_indexer import index_manifest
    manifest_path = Path(manifest)
    if not manifest_path.is_file():
        raise typer.BadParameter('Manifest file not found')
    out_dir = Path(out)
    index_manifest(manifest_path, out_dir, limit=limit)
    success(f'Corpus indexed to {out_dir}')


@app.command('corpus-learn')
def corpus_learn(
    kb: str = typer.Option(..., help='Path to the SQLite knowledge store'),
    out: str = typer.Option('outputs/corpus', help='Output directory for learning results'),
) -> None:
    """Run the learning step on the indexed corpus.

    Currently a placeholder that creates ``learning_summary.json``.
    """
    from src.corpus.corpus_learner import learn_corpus
    kb_path = Path(kb)
    out_dir = Path(out)
    learn_corpus(kb_path, out_dir)
    success(f'Learning completed, summary written to {out_dir / "learning_summary.json"}')


@app.command('corpus-query')
def corpus_query(
    kb: str = typer.Option(..., help='Path to the SQLite knowledge store'),
    query: str = typer.Option(..., help='Natural language query string'),
) -> None:
    """Execute a query against the corpus knowledge base.

    This is a stub – it returns a placeholder result.
    """
    from src.corpus.corpus_query import query_corpus
    result = query_corpus(Path(kb), query)
    console.print_json(data=result)


@app.command('corpus-report')
def corpus_report(
    kb: str = typer.Option(..., help='Path to the SQLite knowledge store'),
    out: str = typer.Option('outputs/corpus/report.md', help='Output markdown report path'),
) -> None:
    """Generate a markdown report for the corpus.

    Placeholder implementation creates a minimal report file.
    """
    from src.corpus.report_builder import build_report
    kb_path = Path(kb)
    out_path = Path(out)
    build_report(kb_path, out_path)
    success(f'Report generated: {out_path}')


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


# ---------------------------------------------------------------------------
# Company Drafting Profile commands
# ---------------------------------------------------------------------------

@app.command('company-profile-build')
def company_profile_build(
    repo_root: str = typer.Option(..., help='Path to repository root'),
    out: str = typer.Option('outputs/company_profile', help='Output directory for the profile'),
) -> None:
    """Extract drafting rules from repository files and write a profile JSON."""
    profile = build_company_drafting_profile(Path(repo_root))
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'company_drafting_profile.json'
    write_profile_to_file(profile, out_path)
    success(f'Company drafting profile written: {out_path}')


@app.command('company-profile-show')
def company_profile_show(
    profile: str = typer.Option(..., help='Path to a company drafting profile JSON file'),
) -> None:
    """Print the drafting profile JSON in a pretty format."""
    p = Path(profile)
    if not p.is_file():
        raise typer.BadParameter('Profile file not found')
    data = json.loads(p.read_text(encoding='utf-8'))
    console.print_json(data=data)
