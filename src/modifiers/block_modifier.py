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
