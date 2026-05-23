import os
import ezdxf
from src.workers.experimental_cad_evidence_worker import run_ezdxf_evidence_worker

def create_mock_dxf(filepath: str):
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # 1. Closed Polyline (WAL1 Layer)
    polyline = msp.add_lwpolyline(
        [(0, 0), (10, 0), (10, 5), (0, 5)],
        dxfattribs={'layer': 'WAL1'}
    )
    polyline.closed = True
    
    # 2. Text (ROOM-TEXT Layer)
    msp.add_text(
        "ROOM 101",
        dxfattribs={'layer': 'ROOM-TEXT', 'insert': (5, 2.5)}
    )
    
    # 3. Dimension (DIM Layer) - Aligned Dimension
    # ezdxf의 add_aligned_dim은 DimStyleOverride를 리턴하며, 실제 DXF entity는 dim.dimension에 있음.
    dim = msp.add_aligned_dim(
        p1=(0, -2), p2=(10, -2), distance=1.5,
        dxfattribs={'layer': 'DIM'}
    )
    dim.dimension.dxf.text = "10000"
    dim.dimension.dxf.actual_measurement = 10000.0
    
    doc.saveas(filepath)
    print(f"Mock DXF generated: {filepath}")

def main():
    filepath = "sample.dxf"
    out_dir = "outputs/experimental_cad_evidence_verify"
    
    # Create the test DXF
    create_mock_dxf(filepath)
    
    # Run the ezdxf evidence worker
    print("Running ezdxf evidence worker...")
    run_ezdxf_evidence_worker(filepath, out_dir)
    
    # Check outputs
    json_path = os.path.join(out_dir, "EXPERIMENTAL_CAD_EVIDENCE.json")
    md_path = os.path.join(out_dir, "EXPERIMENTAL_CAD_EVIDENCE.md")
    
    assert os.path.exists(json_path), f"{json_path} does not exist!"
    assert os.path.exists(md_path), f"{md_path} does not exist!"
    
    print("\n[SUCCESS] ezdxf offline evidence worker verified perfectly!")
    print(f"- Output JSON: {json_path}")
    print(f"- Output MD  : {md_path}")
    
    # Cleanup mock DXF
    if os.path.exists(filepath):
        os.remove(filepath)
        print("Cleaned up mock DXF.")

if __name__ == "__main__":
    main()
