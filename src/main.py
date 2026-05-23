from __future__ import annotations

import importlib

from src.utils.encoding import ensure_utf8_stdio

ensure_utf8_stdio()

from src.app.cli import app


def _register_cli_module(module_name: str) -> bool:
    """Import a CLI extension module when it exists.

    Some integration branches add CLI modules before they land on main. Keeping
    the module list here lets those commands register automatically after merge,
    while current main remains runnable. Only the target CLI module itself may be
    absent; missing dependencies inside an existing module are real errors and
    must not be swallowed.
    """
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            return False
        raise
    return True


for _module_name in (
    "src.app.intelligent_cli",
    "src.app.orchestrated_cli",
    "src.app.xicad_stage2_cli",
    "src.app.xicad_contract_cli",
    "src.app.xicad_contract_workbench_cli",
    "src.app.xicad_manual_recorder_cli",
    "src.app.autopilot_cli",
    "src.app.landscape_sync_cli",
    "src.app.corpus_cli",
    "src.app.open_tools_cli",
    "src.app.router_cli",
    "src.app.route_plan_cli",
    "src.app.webhard_cli",
    "src.app.webhard_batch_cli",
    "src.app.converters_cli",
    "src.app.run_summary_cli",
    "src.app.text_roles_cli",
    "src.app.open_backends_cli",
    "src.app.spatial_cli",
    "src.app.spatial_graph_cli",
    "src.app.cad_platforms_cli",
    "src.app.layer_analysis_cli",
    "src.app.layer_audit_cli",
    "src.app.fusion_matrix_cli",
    "src.app.cross_validate_cli",
    "src.app.shapely_topology_cli",
    "src.app.shapely_area_match_cli",
    "src.app.shapely_topology_audit_cli",
    "src.app.worker_cli",
):
    _register_cli_module(_module_name)


if __name__ == '__main__':
    app()
