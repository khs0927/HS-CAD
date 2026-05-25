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
import src.app.xicad_policy_candidate_cli  # noqa: F401,E402
import src.app.xicad_alias_allowlist_cli  # noqa: F401,E402
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
import src.app.domain_rules_cli  # noqa: F401,E402
import src.app.domain_rule_decision_cli  # noqa: F401,E402
import src.app.domain_rule_command_plan_cli  # noqa: F401,E402
import src.app.domain_rule_review_gate_cli  # noqa: F401,E402
import src.app.safe_execution_cli  # noqa: F401,E402
import src.app.zwcad_copy_validation_cli  # noqa: F401,E402

if __name__ == '__main__':
    app()
