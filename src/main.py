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
import src.app.reviewcontext_dxf_cli  # noqa: F401,E402

# Analysis Megapack integrations
import src.app.analysis_shortcut_cli  # noqa: F401,E402
import src.app.analysis_shortcut_cli_v2  # noqa: F401,E402
import src.app.analysis_shortcut_cli_v3  # noqa: F401,E402
import src.app.analysis_pipeline_cli  # noqa: F401,E402
import src.app.analysis_phase3_cli  # noqa: F401,E402
import src.app.analysis_phase4_cli  # noqa: F401,E402
import src.app.analysis_phase5_cli  # noqa: F401,E402
import src.app.analysis_phase6_cli  # noqa: F401,E402
import src.app.analysis_phase7_9_cli  # noqa: F401,E402
import src.app.analysis_phase10_11_cli  # noqa: F401,E402
import src.app.analysis_phase12_cli  # noqa: F401,E402
import src.app.final_todo_cli  # noqa: F401,E402
import src.app.main_readiness_cli  # noqa: F401,E402
import src.app.post_pr53_main_readiness_cli  # noqa: F401,E402
import src.app.main_merge_readiness_cli  # noqa: F401,E402
import src.app.pr55_main_ready_cli  # noqa: F401,E402
import src.app.main_merge_operator_review_cli  # noqa: F401,E402
import src.app.post_main_local_validation_cli  # noqa: F401,E402
import src.app.human_main_merge_review_cli  # noqa: F401,E402
import src.app.local_validation_recorder_cli  # noqa: F401,E402
import src.app.final_live_runner_safety_spec_cli  # noqa: F401,E402






if __name__ == '__main__':
    app()
