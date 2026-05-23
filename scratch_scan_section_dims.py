# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
from collections import Counter

def main():
    try:
        zwcad = win32com.client.Dispatch("ZWCAD.Application")
        doc = zwcad.ActiveDocument
        ms = doc.ModelSpace
        
        print(f"Active Document: {doc.Name}")
        print("Scanning objects in ModelSpace...")
        
        counts = Counter()
        dims = []
        beams = []
        
        for i in range(ms.Count):
            try:
                obj = ms.Item(i)
                layer = obj.Layer.upper()
                obj_name = obj.ObjectName
                
                counts[obj_name] += 1
                
                # 수집: 치수 객체
                if "Dimension" in obj_name:
                    txt = getattr(obj, "TextOverride", "") or getattr(obj, "Measurement", 0.0)
                    dims.append({"layer": layer, "text": txt, "type": obj_name})
                    
                # 수집: 철골/보/기둥 레이어의 폴리라인이나 선
                if "BEAM" in layer or "COL" in layer or "STEEL" in layer:
                    if "Polyline" in obj_name or "Line" in obj_name:
                        beams.append({"layer": layer, "type": obj_name})
            except Exception:
                pass
                
        print("\n--- Object Types Count ---")
        for k, v in counts.most_common():
            print(f"{k}: {v}")
            
        print(f"\n--- Dimensions Found ({len(dims)}) ---")
        for d in dims[:20]:
            print(d)
            
        print(f"\n--- Beams/Columns Found ({len(beams)}) ---")
        for b in beams[:20]:
            print(b)
            
    except Exception as e:
        print(f"Error scanning ZWCAD: {e}")

if __name__ == "__main__":
    main()
