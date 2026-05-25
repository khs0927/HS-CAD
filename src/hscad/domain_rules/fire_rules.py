from __future__ import annotations

from hscad.core.models import FileizedDrawing
from hscad.domain_rules.base import RuleResult, RuleStatus


class FireOpeningReviewRule:
    rule_id = "FIRE_OPENING_REVIEW_REQUIRED"

    def evaluate(self, drawing: FileizedDrawing) -> RuleResult:
        openings = [e for e in drawing.entities if e.layer.upper() in {"WIN", "WINBAR", "WINELE", "DOOR", "DOOR_SWING"}]
        if openings:
            return RuleResult(self.rule_id, RuleStatus.REVIEW, 0.68, "Opening candidates found; firefighter entry/window and egress rules require project-specific code review", recommended_action="manual_code_review_required", data={"opening_count": len(openings)})
        return RuleResult(self.rule_id, RuleStatus.REVIEW, 0.42, "No opening candidates found; cannot verify fire entry/egress from current evidence", recommended_action="review_opening_layers")
