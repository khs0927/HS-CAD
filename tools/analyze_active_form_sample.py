import comtypes.client
import json
import sys
from pathlib import Path

def main():
    try:
        print("Connecting to ZWCAD 2026 COM...")
        try:
            app = comtypes.client.GetActiveObject("ZWCAD.Application.2026")
        except Exception:
            print("Error: ZWCAD 2026 instance is not running or not accessible via COM.")
            sys.exit(1)
            
        doc = app.ActiveDocument
        print(f"Connected to drawing: {doc.Name}")
        print("Sampling layer configurations directly from the CAD database (O(1) instant scan)...")
        
        # Normalize target layers
        target_layers = {"WALL1", "글씨", "치수", "중심선", "옹벽", "COL"}
        sampled_styles = {}
        
        # Loop through drawing layers to get parent property values (ByLayer standard)
        for i in range(doc.Layers.Count):
            layer = doc.Layers.Item(i)
            name = layer.Name
            name_upper = name.upper()
            
            # Match target layers
            if name_upper in target_layers or any(t in name_upper for t in target_layers):
                color = layer.Color
                linetype = layer.Linetype
                lineweight = getattr(layer, "Lineweight", -1)
                
                # Determine standard text height based on typical ZIUM architectural standards:
                # - Title/Room names: 250.0 ~ 300.0 mm
                # - Standard notes/details: 150.0 ~ 200.0 mm
                text_height = 150.0
                if "글씨" in name_upper or "평면" in name_upper or "NAME" in name_upper:
                    text_height = 250.0
                elif "COL" in name_upper or "WALL" in name_upper or "옹벽" in name_upper:
                    text_height = 0.0 # Non-text geometry layers
                    
                sampled_styles[name] = {
                    "layer_name": name,
                    "color": color,
                    "linetype": linetype,
                    "lineweight": lineweight,
                    "text_height": text_height,
                    "text_style": doc.ActiveTextStyle.Name if hasattr(doc, "ActiveTextStyle") else "Standard",
                    "dimension_style": doc.ActiveDimStyle.Name if hasattr(doc, "ActiveDimStyle") else "Standard"
                }
                
        out_dir = Path("C:/zwcad-ai-modifier-xicad-next-complete/zwcad-ai-modifier/generated")
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "sampled_drawing_grammar.json"
        
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(sampled_styles, f, ensure_ascii=False, indent=2)
            
        print(f"\n[SUCCESS] Surrounding drafting styles sampled and saved!")
        print(f"Grammar styles written to: {out_path}")
        print(json.dumps(sampled_styles, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"Error analyzing active styles: {e}")

if __name__ == "__main__":
    main()
