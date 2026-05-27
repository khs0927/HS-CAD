# -*- coding: utf-8 -*-
"""
Replicate Drawing2.dwg element-by-element into a new drawing in ZWCAD 2024.
Uses EntityName pre-filtering to avoid custom proxy freezes and flushes prints immediately.
"""
import sys
import os
from pathlib import Path

def main():
    print("=" * 80, flush=True)
    print("ZWCAD 2024 - Live Element-by-Element Drawing Replication v3", flush=True)
    print("=" * 80, flush=True)

    try:
        import win32com.client
    except ImportError:
        print("[FAIL] win32com.client not found. Please install pywin32.", flush=True)
        return

    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application.2024")
    except Exception as e:
        print(f"[FAIL] Could not connect to ZWCAD 2024: {e}", flush=True)
        return

    # 1. Locate Drawing2.dwg
    doc2 = None
    for doc in app.Documents:
        if doc.Name.lower() == "drawing2.dwg":
            doc2 = doc
            break

    if not doc2:
        print("[FAIL] Drawing2.dwg is not open in ZWCAD 2024.", flush=True)
        print(f"Open documents: {[d.Name for d in app.Documents]}", flush=True)
        return

    print(f"[SUCCESS] Found active document: {doc2.Name}", flush=True)
    
    # 2. Create a brand new drawing (using zwcad.dwt to bypass template prompt dialog)
    print("Creating a new drawing in ZWCAD 2024 using zwcad.dwt...", flush=True)
    try:
        new_doc = app.Documents.Add("zwcad.dwt")
        print(f"[SUCCESS] Created new drawing: {new_doc.Name}", flush=True)
    except Exception as e:
        print(f"[FAIL] Could not create new drawing: {e}", flush=True)
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
                return None

    # 3. Pre-scan and filter standard entities first
    print("Pre-scanning ModelSpace entities...", flush=True)
    standard_objs = []
    scanned_count = 0
    
    for obj in doc2.ModelSpace:
        scanned_count += 1
        try:
            # Get EntityName (very fast and never hangs on proxy objects)
            ent_name = obj.EntityName
            
            # Supported standard entity types
            if ent_name in (
                "AcDbLine", "AcDbPolyline", "AcDb2dPolyline", "AcDb3dPolyline",
                "AcDbText", "AcDbMText", "AcDbCircle", "AcDbArc", "AcDbBlockReference"
            ):
                standard_objs.append((ent_name, obj))
            
            if scanned_count % 100 == 0:
                print(f"  Pre-scanned {scanned_count} entities...", flush=True)
        except Exception:
            continue

    print(f"Pre-scan completed. Found {len(standard_objs)} standard entities to replicate out of {scanned_count}.", flush=True)

    # 4. Draw standard entities one by one into the new drawing
    drawn_count = 0
    print("Drawing standard entities element-by-element...", flush=True)
    
    for ent_name, obj in standard_objs:
        try:
            new_obj = None
            layer = obj.Layer
            color = obj.Color
            ensure_layer(layer)

            if ent_name == "AcDbLine":
                start = list(obj.StartPoint)
                end = list(obj.EndPoint)
                new_obj = new_doc.ModelSpace.AddLine(start, end)
                
            elif ent_name in ("AcDbPolyline", "AcDb2dPolyline"):
                coords = list(obj.Coordinates)
                new_obj = new_doc.ModelSpace.AddLightWeightPolyline(coords)
                try:
                    new_obj.Closed = bool(obj.Closed)
                except Exception:
                    pass
                    
            elif ent_name == "AcDbMText":
                insert = list(obj.InsertionPoint)
                text = obj.TextString
                height = obj.Height
                new_obj = new_doc.ModelSpace.AddMText(insert, 0.0, text)
                try:
                    new_obj.Height = height
                    new_obj.Rotation = obj.Rotation
                except Exception:
                    pass
                    
            elif ent_name == "AcDbText":
                insert = list(obj.InsertionPoint)
                text = obj.TextString
                height = obj.Height
                new_obj = new_doc.ModelSpace.AddText(text, insert, height)
                try:
                    new_obj.Rotation = obj.Rotation
                except Exception:
                    pass
                    
            elif ent_name == "AcDbCircle":
                center = list(obj.Center)
                radius = obj.Radius
                new_obj = new_doc.ModelSpace.AddCircle(center, radius)
                
            elif ent_name == "AcDbArc":
                center = list(obj.Center)
                radius = obj.Radius
                start_angle = obj.StartAngle
                end_angle = obj.EndAngle
                new_obj = new_doc.ModelSpace.AddArc(center, radius, start_angle, end_angle)
                
            elif ent_name == "AcDbBlockReference":
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

            if drawn_count % 100 == 0:
                print(f"  Re-drew {drawn_count} standard entities...", flush=True)
                
        except Exception as e:
            continue

    # 5. Save and Regen the newly drawn document
    print(f"Total re-drawn: {drawn_count}", flush=True)
    try:
        new_doc.Regen(1)
        out_path = r"C:\cad\replicated_drawing2.dwg"
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        new_doc.SaveAs(out_path)
        print(f"[SUCCESS] Replicated {drawn_count} elements into brand new drawing!", flush=True)
        print(f"Saved drawing at: {out_path}", flush=True)
    except Exception as e:
        print(f"[FAIL] Could not save the drawing: {e}", flush=True)

    print("=" * 80, flush=True)

if __name__ == '__main__':
    main()
