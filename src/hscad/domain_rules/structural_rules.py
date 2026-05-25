from __future__ import annotations

from hscad.cad.layer_schema import STRUCTURAL_LAYERS
from hscad.core.models import FileizedDrawing
from hscad.domain_rules.base import RuleResult, RuleStatus


class StructuralLayerPresenceRule:
    rule_id = "STRUCTURAL_LAYER_PRESENCE"

    def evaluate(self, drawing: FileizedDrawing) -> RuleResult:
        structural = [e for e in drawing.entities if e.layer.upper() in STRUCTURAL_LAYERS]
        if structural:
            return RuleResult(self.rule_id, RuleStatus.PASS, 0.8, f"Structural layer candidates present: {len(structural)}", data={"structural_entity_count": len(structural)})
        return RuleResult(self.rule_id, RuleStatus.REVIEW, 0.5, "No canonical structural layer candidates found", recommended_action="review_structural_layer_mapping")
