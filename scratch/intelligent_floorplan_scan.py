# -*- coding: utf-8 -*-
import win32com.client
import sys

def intelligent_floorplan_scan():
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
        ms = doc.ModelSpace
    except Exception as e:
        sys.exit(1)

    print("--- 1. Scanning Floorplan Extents and Layers ---")
    layer_counts = {}
    x_coords = []
    
    # We will sample the first 2000 objects to guess the main drawing area
    sample_size = min(ms.Count, 2000)
    
    for i in range(sample_size):
        try:
            ent = ms.Item(i)
            # Count layers
            layer = ent.Layer
            layer_counts[layer] = layer_counts.get(layer, 0) + 1
            
            # Get X coords for bound calculation
            x = None
            if hasattr(ent, 'InsertionPoint'): x = ent.InsertionPoint[0]
            elif hasattr(ent, 'StartPoint'): x = ent.StartPoint[0]
            elif hasattr(ent, 'Coordinates') and len(ent.Coordinates) > 0: x = ent.Coordinates[0]
            
            if x is not None:
                x_coords.append(x)
        except:
            pass

    sorted_layers = sorted(layer_counts.items(), key=lambda item: item[1], reverse=True)
    print("\nTop 10 Layers in Drawing:")
    for l, count in sorted_layers[:10]:
        print(f"Layer: {l}, Count: {count}")
        
    if x_coords:
        min_x = min(x_coords)
        max_x = max(x_coords)
        print(f"\nSampled X-Bounds: Min X = {min_x:.2f}, Max X = {max_x:.2f}")

    print("\n--- 2. Logical Deduction for Section ---")
    print("Based on the layers, the section must inherit the exact same layers (e.g. CEN, WALL1, COL).")
    print("The section should be vertically projected from the main floor plan, keeping X-coordinates consistent if possible, or placed neatly to the right.")

if __name__ == "__main__":
    intelligent_floorplan_scan()
