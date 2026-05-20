from __future__ import annotations

from typing import Any

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
    objects: list[dict[str, Any]],
    target_block: str,
    new_block: str,
    layer: str | None = None,
    preserve_rotation: bool = True,
    preserve_scale: bool = True,
    preserve_layer: bool = True,
    delete_original: bool = True,
    known_blocks: list[str] | None = None,
) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for obj in objects:
        names = {str(obj.get("name") or ""), str(obj.get("effective_name") or "")}
        if target_block not in names:
            continue
        if layer and obj.get("layer") != layer:
            continue
        matches.append({
            "handle": obj.get("handle"),
            "insert": obj.get("insert"),
            "rotation": obj.get("rotation") if preserve_rotation else 0,
            "x_scale": obj.get("x_scale") if preserve_scale else 1,
            "y_scale": obj.get("y_scale") if preserve_scale else 1,
            "z_scale": obj.get("z_scale") if preserve_scale else 1,
            "layer": obj.get("layer") if preserve_layer else layer,
            "attributes": obj.get("attributes", []),
        })
    warnings: list[str] = []
    if known_blocks is not None and new_block not in known_blocks:
        warnings.append("new block definition missing")
    if matches:
        warnings.append("attribute mapping is best-effort and must be verified in real ZWCAD")
    return {
        "action": "replace_block",
        "target_block": target_block,
        "new_block": new_block,
        "layer": layer,
        "delete_original": delete_original,
        "count": len(matches),
        "matches": matches,
        "warnings": warnings,
    }
