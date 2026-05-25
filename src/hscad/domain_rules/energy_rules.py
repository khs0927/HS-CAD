from __future__ import annotations

from hscad.core.models import FileizedDrawing
from hscad.domain_rules.base import RuleResult, RuleStatus


class EnvelopeEnergyReviewRule:
    rule_id = "ENERGY_ENVELOPE_REVIEW_REQUIRED"

    def evaluate(self, drawing: FileizedDrawing) -> RuleResult:
        windows = [e for e in drawing.entities if e.layer.upper() in {"WIN", "WINBAR", "WINELE"}]
        return RuleResult(
            self.rule_id,
            RuleStatus.REVIEW,
            0.55 if windows else 0.35,
            "Envelope U-value compliance needs specification evidence in addition to geometry",
            recommended_action="attach_window_panel_spec_and_manual_review",
            data={"window_candidate_count": len(windows)},
        )
