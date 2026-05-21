"""Import shim for the isolated image-to-CAD package.

The implementation lives under ``src/neuro_seq_cad`` so it stays separated
from the existing ``src.main`` ZWCAD workflow. This shim lets users run:

    python -m neuro_seq_cad.app.cli
"""

from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parents[1] / "src" / "neuro_seq_cad"
if _SRC_PACKAGE.exists():
    __path__.append(str(_SRC_PACKAGE))  # type: ignore[name-defined]

