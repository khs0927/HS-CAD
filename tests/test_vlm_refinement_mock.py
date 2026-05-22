from __future__ import annotations
import sys
from pathlib import Path
import pytest

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

def test_vlm_refinement_mock():
    """Test VLM refinement mock execution and target matching on the EvidenceGraph."""
    from neuro_seq_cad.fusion.evidence_graph import EvidenceGraph, EvidenceEntity, PipelineMeta, BBox
    from neuro_seq_cad.vlm.vlm_client import VLMRefinementClient
    from neuro_seq_cad.vlm.vlm_refiner import VLMFloorplanRefiner
    
    # 1. Create a dummy graph containing 'Bath' room and a door
    meta = PipelineMeta(
        pipeline_version="0.1.0",
        image_path="test.png",
        image_width=1200,
        image_height=800,
        scale_pixels_per_mm=1.0,
        active_sources=["mock"]
    )
    graph = EvidenceGraph(pipeline=meta)
    
    bath_room = EvidenceEntity(
        entity_type="room",
        text="Bath",
        confidence=0.8,
        bbox=BBox(x1=100.0, y1=100.0, x2=200.0, y2=200.0)
    )
    door_ent = EvidenceEntity(
        entity_type="door",
        confidence=0.8,
        bbox=BBox(x1=150.0, y1=195.0, x2=190.0, y2=205.0)
    )
    door_ent.add_source(name="raster2seq_mock", confidence=0.8)
    
    graph.entities.extend([bath_room, door_ent])
    
    # 2. Request mock refinement feedback
    client = VLMRefinementClient(api_key="")  # Empty key triggers Mock mode
    assert not client.is_available()
    
    feedback = client.request_refinement(Path("test.png"), vector_data_json=graph.model_dump_json())
    assert feedback.quality_score == 0.92
    assert len(feedback.instructions) == 2
    
    # 3. Apply VLM refinement
    refiner = VLMFloorplanRefiner()
    refined_graph = refiner.refine(graph, feedback)
    
    # Verify that the bath room name was successfully renamed to 'Bathroom'
    refined_bath = refined_graph.by_id(bath_room.id)
    assert refined_bath is not None
    assert refined_bath.text == "Bathroom"
    
    # Verify that the door position shifted by Y-axis -5.0px
    refined_door = refined_graph.by_id(door_ent.id)
    assert refined_door is not None
    assert refined_door.bbox.y1 == 190.0  # 195.0 - 5.0
    assert refined_door.bbox.y2 == 200.0  # 205.0 - 5.0
