"""DWG reader that uses the existing ZWCAD COM adapter.

The function opens a DWG in read‑only mode, extracts basic information and
closes the document without modifying anything.  It returns a lightweight
dictionary that can later be transformed into a canonical knowledge record.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.scanners.layer_scanner import layer_counts
from src.scanners.block_scanner import block_summary
from src.scanners.text_scanner import extract_texts


def read_dwg(dwg_path: Path) -> Dict[str, Any]:
    """Read *dwg_path* and return extracted information.

    The returned dictionary contains:
        - ``objects``: raw object list from the adapter
        - ``layer_summary``: dict of layer → count
        - ``block_summary``: dict of block name → summary dict
        - ``texts``: list of extracted text items
    """

    adapter = ZWCADCOMAdapter(visible=False)
    try:
        # Open the drawing – the adapter implementation opens it read‑only.
        adapter.open_document(str(dwg_path))
        objects = adapter.scan_modelspace()
        # Extract simple summaries
        layers = layer_counts(objects)
        blocks = block_summary(objects)
        texts = extract_texts(objects)
        return {
            "objects": objects,
            "layer_summary": layers,
            "block_summary": blocks,
            "texts": texts,
        }
    finally:
        # Ensure the document is closed even if an exception occurs
        try:
            adapter.close()
        except Exception:
            pass
