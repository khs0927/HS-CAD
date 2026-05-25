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

def main():
    try:
        temp_dxf = Path("outputs/sample/temp_fast_scan.dxf")
        if not temp_dxf.exists():
            print(f"Error: {temp_dxf} does not exist.")
            return
            
        print(f"Parsing existing DXF: {temp_dxf}...")
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
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
