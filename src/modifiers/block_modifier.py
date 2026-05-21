from __future__ import annotations

from src.cad_core.base import CADAdapter


def list_blocks(adapter: CADAdapter) -> list[str]:
    return adapter.list_blocks()


def replace_block(adapter, target_block: str, new_block: str, layer: str | None = None) -> dict:
    if hasattr(adapter, 'replace_block'):
        return adapter.replace_block(target_block, new_block, layer)
    return {
        'status': 'adapter_missing_replace_block',
        'target_block': target_block,
        'new_block': new_block,
        'layer': layer,
    }


def replace_block_plan(
    entities: list[dict],
    target_block: str,
    new_block: str,
    layer: str | None = None,
    known_blocks: list[str] | None = None,
) -> dict:
    known = set(known_blocks or [])
    matches = [
        entity for entity in entities
        if entity.get("entity_type") == "INSERT"
        and entity.get("name") == target_block
        and (layer is None or entity.get("layer") == layer)
    ]
    warnings: list[str] = []
    if new_block not in known:
        warnings.append("new block definition missing")
    return {
        "action": "replace_block",
        "target_block": target_block,
        "new_block": new_block,
        "layer": layer,
        "count": len(matches),
        "matches": matches,
        "warnings": warnings,
    }
