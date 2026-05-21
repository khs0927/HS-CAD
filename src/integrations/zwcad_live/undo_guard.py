"""Undo guard wrapper for ZWCAD live integration.

The original implementation lives in ``image_to_cad.auto.undo_guard``.
This thin wrapper re‑exports the same public helpers so that orchestrator
code can import them from ``integrations.zwcad_live.undo_guard`` without
duplicating logic.
"""

from image_to_cad.auto.undo_guard import create_undo_mark, undo_back_to_mark, block_purge_delete_explode

__all__ = ["create_undo_mark", "undo_back_to_mark", "block_purge_delete_explode"]
