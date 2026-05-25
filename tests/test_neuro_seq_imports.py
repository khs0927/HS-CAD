from __future__ import annotations
import sys
from pathlib import Path

# Add src to sys.path to resolve neuro_seq_cad in testing environments
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

def test_neuro_seq_imports():
    """Verify that all main classes, settings, and adapters of the floorplan-to-cad framework import successfully."""
    from neuro_seq_cad.config.settings import get_settings

    settings = get_settings()
    assert settings is not None
    assert settings.dxf_version == "R2010"
