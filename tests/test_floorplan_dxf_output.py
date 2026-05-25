from __future__ import annotations
import sys
from pathlib import Path
import ezdxf

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

def test_floorplan_dxf_output(tmp_path):
    """Test generating a DXF drawing using DXFBuilder, and smoke test its contents with ezdxf."""
    from neuro_seq_cad.app.cli import analyze
    
    # Generate DXF via dry run E2E
    dummy_image = tmp_path / "test_plan.png"
    analyze(image=dummy_image, output_dir=tmp_path, dry_run=True, vlm_refine=True)
    
    dxf_path = tmp_path / "synthetic_floorplan.dxf"
    assert dxf_path.exists()
    
    # Load DXF using ezdxf
    doc = ezdxf.readfile(dxf_path)
    assert doc is not None
    
    # Check that required layers are registered
    expected_layers = {"WAL1", "DOOR", "WIN", "COL", "TEXT", "DIM"}
    registered_layers = {layer.dxf.name for layer in doc.layers}
    
    for layer in expected_layers:
        assert layer in registered_layers, f"Layer {layer} was not found in DXF layers: {registered_layers}"
        
    # Check that there are drawing entities in the model space
    msp = doc.modelspace()
    entities = list(msp)
    assert len(entities) > 0, "Model space has 0 entities."
    
    # Verify entity types (e.g. LINES, LWPOLYLINES, TEXT, INSERT blocks)
    entity_types = {ent.dxftype() for ent in entities}
    assert any(etype in {"LINE", "LWPOLYLINE"} for etype in entity_types), "No lines or polylines were found."
    assert "TEXT" in entity_types or "MTEXT" in entity_types, "No text entities were found."
    assert "INSERT" in entity_types, "No block inserts (doors/windows/columns) were found."
