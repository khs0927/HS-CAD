from __future__ import annotations

from hscad.core.models import FileizedDrawing
from hscad.domain_rules.base import RuleResult, RuleStatus


class XiCadPlanOnlyRule:
    rule_id = "XICAD_PLAN_ONLY_SAFETY"

    def evaluate(self, drawing: FileizedDrawing) -> RuleResult:
        return RuleResult(
            self.rule_id,
            RuleStatus.PASS,
            1.0,
            "XiCAD command execution is disabled; this rule only prepares review evidence",
            recommended_action="keep_xicad_alias_execution_disabled",
            data={"xicad_alias_execution_allowed": False},
        )
