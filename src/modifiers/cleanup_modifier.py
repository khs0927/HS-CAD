from __future__ import annotations


def planned_cleanup() -> list[dict]:
    return [{'action': 'audit'}, {'action': 'purge'}, {'action': 'overkill_if_supported'}]


def delete_layer_objects(adapter, layer: str) -> dict:
    if hasattr(adapter, 'delete_layer_objects'):
        return {'deleted': adapter.delete_layer_objects(layer)}
    return {'status': 'adapter_missing_delete_layer_objects', 'layer': layer}
