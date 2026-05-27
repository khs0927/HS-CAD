# -*- coding: utf-8 -*-
"""
Fast audit of layers, entity types, colors, and block references in Drawing2.dwg.
"""
import sys
from collections import Counter, defaultdict

def main():
    print("=" * 80, flush=True)
    print("Drawing2.dwg Fast Layer & Entity Audit", flush=True)
    print("=" * 80, flush=True)

    try:
        import win32com.client
    except ImportError:
        print("[FAIL] win32com.client not found.", flush=True)
        return

    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application.2024")
    except Exception as e:
        print(f"[FAIL] Could not connect to ZWCAD 2024: {e}", flush=True)
        return

    # Locate Drawing2.dwg
    doc2 = None
    for doc in app.Documents:
        if doc.Name.lower() == "drawing2.dwg":
            doc2 = doc
            break

    if not doc2:
        print("[FAIL] Drawing2.dwg is not open in ZWCAD 2024.", flush=True)
        return

    print(f"[SUCCESS] Connected to active document: {doc2.Name}", flush=True)

    layer_summary = defaultdict(lambda: {"types": Counter(), "colors": Counter(), "blocks": Counter()})
    total_count = 0

    print("Scanning entities...", flush=True)
    for obj in doc2.ModelSpace:
        total_count += 1
        try:
            ent_name = obj.EntityName
            layer = obj.Layer
            color = obj.Color
            
            summary = layer_summary[layer]
            summary["types"][ent_name] += 1
            summary["colors"][color] += 1
            
            if ent_name == "AcDbBlockReference":
                summary["blocks"][obj.Name] += 1
        except Exception:
            continue

    print(f"Scan complete. Total entities processed: {total_count}", flush=True)
    print("\nLayer Semantic Breakdown:", flush=True)
    print("-" * 60, flush=True)
    
    for layer, sum_data in sorted(layer_summary.items()):
        print(f"\nLayer: '{layer}' (Total entities: {sum(sum_data['types'].values())})", flush=True)
        print(f"  Entity Types: {dict(sum_data['types'])}", flush=True)
        print(f"  Colors      : {dict(sum_data['colors'])}", flush=True)
        if sum_data["blocks"]:
            print(f"  Blocks      : {dict(sum_data['blocks'])}", flush=True)

    print("=" * 80, flush=True)

if __name__ == '__main__':
    main()
