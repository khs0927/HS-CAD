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
        print(f"Connected to active drawing: {doc.Name}")
        print("Scanning layers and blocks dynamically (instant scan)...")
        
        # 1. Observational Layer Scanning (No mutation, only reading)
        layers = []
        for i in range(doc.Layers.Count):
            layer = doc.Layers.Item(i)
            layers.append({
                "name": layer.Name,
                "color": layer.Color,
                "linetype": layer.Linetype,
                "freeze": layer.Freeze,
                "on": layer.LayerOn
            })
            
        # 2. Block Definition Scanning (Focus on ZIUM title block & fixtures)
        blocks = []
        zium_sheet_found = False
        zium_logo_found = False
        
        for i in range(doc.Blocks.Count):
            block = doc.Blocks.Item(i)
            name = block.Name
            if name.startswith("*"):
                continue
            blocks.append(name)
            if "ZIUM_sheet" in name or "zium_sheet" in name.lower():
                zium_sheet_found = True
            if "ZIUM LOGO" in name or "zium logo" in name.lower():
                zium_logo_found = True
                
        # 3. Read Entity Counts from LISP Audit file if exists
        entity_types = {}
        total_objects = 0
        audit_path = Path("C:/zwcad-ai-modifier-xicad-next-complete/zwcad-ai-modifier/audit.txt")
        if audit_path.exists():
            print("Reading cached entity counts from native LISP audit...")
            try:
                # Read CP949 (Default) or UTF-8
                with open(audit_path, "r", encoding="ansi") as f:
                    lines = f.readlines()
                
                section = None
                for line in lines:
                    line = line.strip()
                    if "Total Objects:" in line:
                        try:
                            total_objects = int(line.split(":")[1].strip())
                        except:
                            pass
                    elif (section and "--- Entity Counts ---" in section) or "--- Entity Counts ---" in line:
                        section = "entities"
                    elif "--- Layer Counts ---" in line or "--- Block Counts ---" in line:
                        section = None
                    elif section == "entities" and ":" in line:
                        parts = line.split(":")
                        entity_types[parts[0].strip()] = int(parts[1].strip())
            except Exception as e:
                print(f"Warning reading audit cache: {e}")
        
        # 4. Generate Grammar Context Report
        grammar_context = {
            "drawing_name": doc.Name,
            "drawing_path": doc.FullName,
            "total_objects": total_objects or doc.ModelSpace.Count,
            "layers_observed": layers,
            "user_blocks_observed": blocks,
            "zium_title_block_present": zium_sheet_found,
            "zium_logo_present": zium_logo_found,
            "entity_frequency": entity_types
        }
        
        out_dir = Path("C:/zwcad-ai-modifier-xicad-next-complete/zwcad-ai-modifier/generated")
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "fast_scan_report.json"
        
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(grammar_context, f, ensure_ascii=False, indent=2)
            
        print(f"\n[SUCCESS] Active Drawing Grammar Scanned!")
        print(f"Total Layers Observed: {len(layers)}")
        print(f"Total Block Styles Catalogued: {len(blocks)}")
        print(f"Zium Sheet Standard Detected: {zium_sheet_found}")
        print(f"Report written to: {out_path}")
        
    except Exception as e:
        print(f"Error scanning active drawing: {e}")

if __name__ == "__main__":
    main()
