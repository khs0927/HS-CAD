# -*- coding: utf-8 -*-
"""
Analyze the geometry, layers, blocks, and coordinates of Drawing2.dwg in ZWCAD 2024
to identify exactly what the lines and layers represent.
"""
import sys
from collections import Counter, defaultdict

def main():
    print("=" * 80)
    print("Drawing2.dwg Geometry & Layer Semantic Precision Audit")
    print("=" * 80)

    try:
        import win32com.client
    except ImportError:
        print("[FAIL] win32com.client not found.")
        return

    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application.2024")
    except Exception as e:
        print(f"[FAIL] Could not connect to ZWCAD 2024: {e}")
        return

    # Locate Drawing2.dwg
    doc2 = None
    for doc in app.Documents:
        if doc.Name.lower() == "drawing2.dwg":
            doc2 = doc
            break

    if not doc2:
        print("[FAIL] Drawing2.dwg is not open in ZWCAD 2024.")
        return

    # Scan and aggregate statistics
    layer_entities = defaultdict(list)
    block_names = Counter()
    total_count = 0

    print("Analyzing entities...")
    for obj in doc2.ModelSpace:
        total_count += 1
        try:
            ent_name = obj.EntityName
            layer = obj.Layer
            color = obj.Color
            
            ent_info = {
                "type": ent_name,
                "color": color,
            }

            if ent_name == "AcDbLine":
                ent_info["length"] = ((obj.EndPoint[0] - obj.StartPoint[0])**2 + (obj.EndPoint[1] - obj.StartPoint[1])**2)**0.5
            elif ent_name in ("AcDbPolyline", "AcDb2dPolyline"):
                coords = list(obj.Coordinates)
                ent_info["num_points"] = len(coords) // 2
            elif ent_name == "AcDbBlockReference":
                block_names[obj.Name] += 1
                ent_info["block_name"] = obj.Name

            layer_entities[layer].append(ent_info)
        except Exception:
            continue

    print(f"Total entities analyzed: {total_count}")
    print("\nLayer Distribution and Geometry Breakdown:")
    print("-" * 60)
    
    for layer, entities in sorted(layer_entities.items()):
        types = Counter(e["type"] for e in entities)
        colors = Counter(e["color"] for e in entities)
        
        print(f"\nLayer: '{layer}' (Total entities: {len(entities)})")
        print(f"  Entity Types: {dict(types)}")
        print(f"  Colors: {dict(colors)}")
        
        # Geometry hints
        if "AcDbLine" in types:
            lengths = [e["length"] for e in entities if e["type"] == "AcDbLine"]
            print(f"  Line Count: {len(lengths)}, Min Length: {min(lengths):.1f}, Max Length: {max(lengths):.1f}, Avg Length: {sum(lengths)/len(lengths):.1f}")
        if "AcDbPolyline" in types or "AcDb2dPolyline" in types:
            pts = [e["num_points"] for e in entities if "Polyline" in e["type"]]
            print(f"  Polyline Count: {len(pts)}, Avg Points: {sum(pts)/len(pts):.1f}")
        
        blocks_on_layer = [e["block_name"] for e in entities if "block_name" in e]
        if blocks_on_layer:
            print(f"  Blocks on this layer: {dict(Counter(blocks_on_layer))}")

    print("\n" + "-" * 60)
    print("Block Reference Summary:")
    for name, count in block_names.most_common():
        print(f"  Block '{name}': {count} references")

    print("=" * 80)

if __name__ == '__main__':
    main()
