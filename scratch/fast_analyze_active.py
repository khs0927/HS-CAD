from __future__ import annotations
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.encoding import ensure_utf8_stdio
ensure_utf8_stdio()

import ezdxf
from collections import Counter, defaultdict
from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter

def main():
    try:
        adapter = ZWCADCOMAdapter(visible=True)
        adapter.connect()
        
        if adapter.app is None:
            print("Failed to connect to ZWCAD app.")
            return
            
        doc = adapter.app.ActiveDocument
        print(f"Active Document Name: {doc.Name}")
        print(f"Active Document Full Path: {doc.FullName}")
        
        # Save a copy as DXF in outputs/sample
        temp_dir = Path("outputs/sample")
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_dxf = temp_dir / "temp_fast_scan.dxf"
        
        print("Saving active drawing as DXF for high-speed analysis...")
        if temp_dxf.exists():
            temp_dxf.unlink()
            
        doc.SaveAs(str(temp_dxf.resolve()))
        print(f"Drawing saved to: {temp_dxf}")
        
        print("Parsing DXF file using ezdxf...")
        dxf_doc = ezdxf.readfile(str(temp_dxf))
        modelspace = dxf_doc.modelspace()
        
        # Fast analysis on dxf doc
        layer_counts = Counter()
        entity_counts = Counter()
        layer_entity_counts = defaultdict(Counter)
        text_samples = []
        
        for entity in modelspace:
            layer = entity.dxf.layer
            dxftype = entity.dxftype()
            
            layer_counts[layer] += 1
            entity_counts[dxftype] += 1
            layer_entity_counts[layer][dxftype] += 1
            
            if dxftype in {"TEXT", "MTEXT"} and len(text_samples) < 20:
                text = ""
                if dxftype == "TEXT":
                    text = entity.dxf.text
                else:
                    text = getattr(entity, "text", "")
                text_samples.append({
                    "layer": layer,
                    "text": text
                })
                
        print("\n=== FAST SCAN REPORT ===")
        print(f"Total entities parsed: {len(modelspace)}")
        print("\n--- Top 15 Layers by Entity Count ---")
        for layer, count in layer_counts.most_common(15):
            print(f"- {layer}: {count} entities")
            
        print("\n--- Entity Type Distribution ---")
        for ent_type, count in entity_counts.most_common():
            print(f"- {ent_type}: {count}")
            
        print("\n--- Text Samples (First 20) ---")
        for idx, sample in enumerate(text_samples):
            print(f"[{idx+1}] Layer: {sample['layer']} | Text: {str(sample['text'])}")
            
    except Exception as e:
        print(f"Error during fast scan: {e}")

if __name__ == "__main__":
    main()
