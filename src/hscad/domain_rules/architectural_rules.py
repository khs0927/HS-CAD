from __future__ import annotations

from hscad.cad.layer_schema import WALL_LAYERS
from hscad.core.models import FileizedDrawing
from hscad.domain_rules.base import RuleResult, RuleStatus


class WallLayerPresenceRule:
    rule_id = "ARCH_WALL_LAYER_PRESENCE"

    def evaluate(self, drawing: FileizedDrawing) -> RuleResult:
        wall_entities = [e for e in drawing.entities if e.layer.upper() in WALL_LAYERS]
        if wall_entities:
            return RuleResult(self.rule_id, RuleStatus.PASS, 0.82, f"Wall candidate layers present: {len(wall_entities)}", data={"wall_entity_count": len(wall_entities)})
        return RuleResult(self.rule_id, RuleStatus.WARNING, 0.45, "No canonical wall layer candidates found", recommended_action="review_layer_mapping")
