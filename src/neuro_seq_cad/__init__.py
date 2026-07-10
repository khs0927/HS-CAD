"""
neuro_seq_cad – Unified Floorplan-to-CAD Framework
===================================================
AI-powered scan-to-DXF pipeline combining Raster2Seq, PlanParser,
MLSD line detection, VLM reasoning, and ezdxf CAD generation.
"""

from __future__ import annotations

import os

# Rich help inserts ANSI style boundaries inside option names on some Windows
# terminals and Click test runners. Keep deterministic plain-text help by
# default; users can opt back into Rich help with HSCAD_RICH_HELP=1.
if os.getenv("HSCAD_RICH_HELP", "0").strip().lower() not in {"1", "true", "yes", "on"}:
    try:
        import typer.core

        typer.core.rich = None
    except Exception:
        pass

__version__ = "0.1.0"
__all__ = ["__version__"]
