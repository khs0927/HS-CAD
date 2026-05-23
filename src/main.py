from __future__ import annotations

from src.utils.encoding import ensure_utf8_stdio

ensure_utf8_stdio()

from src.app.cli import app

import src.app.intelligent_cli  # noqa: F401,E402
import src.app.orchestrated_cli  # noqa: F401,E402
import src.app.xicad_stage2_cli  # noqa: F401,E402
import src.app.xicad_contract_cli  # noqa: F401,E402
import src.app.xicad_contract_workbench_cli  # noqa: F401,E402
import src.app.xicad_manual_recorder_cli  # noqa: F401,E402
import src.app.autopilot_cli  # noqa: F401,E402
import src.app.landscape_sync_cli  # noqa: F401,E402
import src.app.corpus_cli  # noqa: F401,E402
import src.app.open_tools_cli  # noqa: F401,E402
import src.app.router_cli  # noqa: F401,E402
import src.app.route_plan_cli  # noqa: F401,E402
import src.app.webhard_cli  # noqa: F401,E402
import src.app.webhard_batch_cli  # noqa: F401,E402
import src.app.converters_cli  # noqa: F401,E402
import src.app.run_summary_cli  # noqa: F401,E402
import src.app.spatial_cli  # noqa: F401,E402
import src.app.text_roles_cli  # noqa: F401,E402
import src.app.open_backends_cli  # noqa: F401,E402
import src.app.spatial_graph_cli  # noqa: F401,E402

if __name__ == '__main__':
    app()
