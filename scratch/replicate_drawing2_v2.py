# -*- coding: utf-8 -*-
"""
Replicate Drawing2.dwg element-by-element into a new drawing in ZWCAD 2024.
Uses zwcad.dwt to bypass dialogs, and defines blocks dynamically to prevent exceptions.
"""
import sys
import os
from pathlib import Path

def main():
    print("=" * 80)
    print("ZWCAD 2024 - Live Element-by-Element Drawing Replication v2")
    print("=" * 80)

    try:
        import win32com.client
    except ImportError:
        print("[FAIL] win32com.client not found. Please install pywin32.")
        return

    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application.2024")
    except Exception as e:
        print(f"[FAIL] Could not connect to ZWCAD 2024: {e}")
        return

    # 1. Locate Drawing2.dwg
    doc2 = None
    for doc in app.Documents:
        if doc.Name.lower() == "drawing2.dwg":
            doc2 = doc
            break

    if not doc2:
        print("[FAIL] Drawing2.dwg is not open in ZWCAD 2024.")
        print(f"Open documents: {[d.Name for d in app.Documents]}")
        return

    print(f"[SUCCESS] Found active document: {doc2.Name}")
    
    # 2. Create a brand new drawing (using zwcad.dwt to bypass template prompt dialog)
    print("Creating a new drawing in ZWCAD 2024 using zwcad.dwt...")
    try:
        new_doc = app.Documents.Add("zwcad.dwt")
        print(f"[SUCCESS] Created new drawing: {new_doc.Name}")
    except Exception as e:
        print(f"[FAIL] Could not create new drawing: {e}")
        return

    # Helper function to ensure layer exists in new doc
    def ensure_layer(layer_name):
        try:
            return new_doc.Layers.Item(layer_name)
        except Exception:
            try:
                return new_doc.Layers.Add(layer_name)
            except Exception:
                return None

    # Helper function to ensure block exists in new doc
    def ensure_block(block_name):
        try:
            return new_doc.Blocks.Item(block_name)
        except Exception:
            try:
                # Add block with origin [0,0,0]
                blk = new_doc.Blocks.Add([0.0, 0.0, 0.0], block_name)
                # Draw a placeholder inside the block so it is visible
                blk.AddCircle([0.0, 0.0, 0.0], 50.0)
                blk.AddLine([-50.0, 0.0, 0.0], [50.0, 0.0, 0.0])
                blk.AddLine([0.0, -50.0, 0.0], [0.0, 50.0, 0.0])
                return blk
            except Exception as e:
                print(f"Error creating block definition '{block_name}': {e}")
                return None

    # 3. Scan and draw entities from Drawing2.dwg
    print("Processing entities from Drawing2.dwg ModelSpace...")
    drawn_count = 0
    scanned_count = 0
    
    for obj in doc2.ModelSpace:
        scanned_count += 1
        try:
            obj_name = obj.ObjectName.lower()
            new_obj = None

            # Common attributes
            layer = obj.Layer
            color = obj.Color
            ensure_layer(layer)

            if "line" in obj_name and "poly" not in obj_name:
                start = list(obj.StartPoint)
                end = list(obj.EndPoint)
                new_obj = new_doc.ModelSpace.AddLine(start, end)
                
            elif "lwpolyline" in obj_name or "polyline" in obj_name:
                coords = list(obj.Coordinates)
                # AddLightWeightPolyline expects double array of points (x, y)
                # If it's a 3D polyline it might have x, y, z points
                new_obj = new_doc.ModelSpace.AddLightWeightPolyline(coords)
                try:
                    new_obj.Closed = bool(obj.Closed)
                except Exception:
                    pass
                    
            elif "mtext" in obj_name:
                insert = list(obj.InsertionPoint)
                text = obj.TextString
                height = obj.Height
                new_obj = new_doc.ModelSpace.AddMText(insert, 0.0, text)
                try:
                    new_obj.Height = height
                    new_obj.Rotation = obj.Rotation
                except Exception:
                    pass
                    
            elif "text" in obj_name:
                insert = list(obj.InsertionPoint)
                text = obj.TextString
                height = obj.Height
                new_obj = new_doc.ModelSpace.AddText(text, insert, height)
                try:
                    new_obj.Rotation = obj.Rotation
                except Exception:
                    pass
                    
            elif "circle" in obj_name:
                center = list(obj.Center)
                radius = obj.Radius
                new_obj = new_doc.ModelSpace.AddCircle(center, radius)
                
            elif "arc" in obj_name:
                center = list(obj.Center)
                radius = obj.Radius
                start_angle = obj.StartAngle
                end_angle = obj.EndAngle
                new_obj = new_doc.ModelSpace.AddArc(center, radius, start_angle, end_angle)
                
            elif "block" in obj_name or "insert" in obj_name:
                block_name = obj.Name
                insert = list(obj.InsertionPoint)
                xs = obj.XScaleFactor
                ys = obj.YScaleFactor
                zs = obj.ZScaleFactor
                rot = obj.Rotation
                
                ensure_block(block_name)
                new_obj = new_doc.ModelSpace.InsertBlock(insert, block_name, xs, ys, zs, rot)

            if new_obj:
                try:
                    new_obj.Layer = layer
                    new_obj.Color = color
                except Exception:
                    pass
                drawn_count += 1
                
        except Exception as e:
            continue

    # 4. Save and Regen the newly drawn document
    print(f"Scanned: {scanned_count}, Re-drawn: {drawn_count}")
    try:
        new_doc.Regen(1)
        out_path = r"C:\cad\replicated_drawing2.dwg"
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        new_doc.SaveAs(out_path)
        print(f"[SUCCESS] Replicated {drawn_count} elements into brand new drawing!")
        print(f"Saved drawing at: {out_path}")
    except Exception as e:
        print(f"[FAIL] Could not save the drawing: {e}")

    print("=" * 80)

if __name__ == '__main__':
    main()
