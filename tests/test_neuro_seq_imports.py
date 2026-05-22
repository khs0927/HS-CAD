from __future__ import annotations
import sys
from pathlib import Path

# Add src to sys.path to resolve neuro_seq_cad in testing environments
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

def test_neuro_seq_imports():
    """Verify that all main classes, settings, and adapters of the floorplan-to-cad framework import successfully."""
    from neuro_seq_cad.config.settings import get_settings
    from neuro_seq_cad.vlm.vlm_client import VLMRefinementClient
    from neuro_seq_cad.vlm.vlm_refiner import VLMFloorplanRefiner
    from neuro_seq_cad.cad.dxf_builder import DXFBuilder
    from neuro_seq_cad.fusion.evidence_graph import EvidenceGraph
    from neuro_seq_cad.geometry.primitives import Point2D, Line2D, BBox2D
    from neuro_seq_cad.geometry.scale_calibration import calibrate_scale

    settings = get_settings()
    assert settings is not None
    assert settings.dxf_version == "R2010"
