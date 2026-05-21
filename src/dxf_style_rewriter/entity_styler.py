from .layer_mapper import layer_for_styled_entity


def build_rewrite_actions_from_styled_result(styled_result: dict) -> list[dict]:
    actions: list[dict] = []
    for item in styled_result.get("entities", []):
        original = item.get("original_entity") or {}
        layer, reason = layer_for_styled_entity(item)
        actions.append(
            {
                "entity_id": original.get("id"),
                "entity_type": original.get("entity_type"),
                "target_layer": layer,
                "reason": reason,
                "needs_review": bool(item.get("needs_review")),
            }
        )
    return actions
