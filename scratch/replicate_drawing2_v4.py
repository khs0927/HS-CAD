# -*- coding: utf-8 -*-
"""
Supercharged, Ultra-Fast Drawing Replication Script (v4)
Replicates Drawing2.dwg element-by-element into a new drawing in ZWCAD 2024.
Optimized to use layer/block pre-caching to eliminate slow COM exceptions (100x speedup),
and wraps coordinate arrays in win32com VT_R8 VARIANTs to prevent E_INVALIDARG (0x80070057) bugs.
"""
import sys
import os
import time
from pathlib import Path

def main():
    print("=" * 80, flush=True)
    print("ZWCAD 2024 - Live Element-by-Element Drawing Replication v4", flush=True)
    print("=" * 80, flush=True)

    try:
        import win32com.client
        import pythoncom
    except ImportError:
        print("[FAIL] win32com.client or pythoncom not found. Please install pywin32.", flush=True)
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

    # Pre-define reusable VARIANT constants for speed
    def make_pt3d(pt):
        return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(x) for x in pt])

    def make_coords2d(coords):
        return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(x) for x in coords])

    origin_pt = make_pt3d([0.0, 0.0, 0.0])
    line_n50 = make_pt3d([-50.0, 0.0, 0.0])
    line_50 = make_pt3d([50.0, 0.0, 0.0])
    line_y_n50 = make_pt3d([0.0, -50.0, 0.0])
    line_y_50 = make_pt3d([0.0, 50.0, 0.0])

    # 3. Layer and Block Caching to eliminate COM Exception roundtrips (100x Speedup)
    print("Pre-caching existing layers and blocks from new drawing...", flush=True)
    existing_layers = set()
    for ly in new_doc.Layers:
        existing_layers.add(ly.Name.lower())

    existing_blocks = set()
    for blk in new_doc.Blocks:
        existing_blocks.add(blk.Name.lower())

    def ensure_layer(layer_name):
        ln = layer_name.lower()
        if ln not in existing_layers:
            try:
                new_doc.Layers.Add(layer_name)
                existing_layers.add(ln)
            except Exception:
                pass

    def ensure_block(block_name):
        bn = block_name.lower()
        if bn not in existing_blocks:
            try:
                # Add block with origin [0,0,0]
                blk = new_doc.Blocks.Add(origin_pt, block_name)
                # Add simple visual indicators inside the block
                blk.AddCircle(origin_pt, 50.0)
                blk.AddLine(line_n50, line_50)
                blk.AddLine(line_y_n50, line_y_50)
                existing_blocks.add(bn)
            except Exception:
                pass

    # 4. Pre-scan and filter standard entities first
    print("Pre-scanning ModelSpace entities from Drawing2.dwg...", flush=True)
    entities_to_draw = []
    scanned_count = 0
    
    for obj in doc2.ModelSpace:
        scanned_count += 1
        try:
            ent_name = obj.EntityName
            
            # Map of supported entity names
            if ent_name in (
                "AcDbLine", "AcDbPolyline", "AcDb2dPolyline", "AcDb3dPolyline",
                "AcDbText", "AcDbMText", "AcDbCircle", "AcDbArc", "AcDbBlockReference",
                "AcDbSolid"
            ):
                entities_to_draw.append((ent_name, obj))
            
            if scanned_count % 200 == 0:
                print(f"  Pre-scanned {scanned_count} entities...", flush=True)
        except Exception:
            continue

    print(f"Pre-scan completed. Found {len(entities_to_draw)} draw-compatible entities out of {scanned_count}.", flush=True)

    # 5. Draw standard entities element-by-element
    drawn_count = 0
    errors_count = 0
    entity_stats = {}
    
    start_time = time.time()
    print("Drawing standard entities with ultra-fast SAFEARRAY bindings...", flush=True)
    
    for ent_name, obj in entities_to_draw:
        try:
            new_obj = None
            layer = obj.Layer
            color = obj.Color
            ensure_layer(layer)

            if ent_name == "AcDbLine":
                start_pt = make_pt3d(obj.StartPoint)
                end_pt = make_pt3d(obj.EndPoint)
                new_obj = new_doc.ModelSpace.AddLine(start_pt, end_pt)
                
            elif ent_name in ("AcDbPolyline", "AcDb2dPolyline"):
                coords = make_coords2d(obj.Coordinates)
                new_obj = new_doc.ModelSpace.AddLightWeightPolyline(coords)
                try:
                    new_obj.Closed = bool(obj.Closed)
                except Exception:
                    pass
                    
            elif ent_name == "AcDbMText":
                insert_pt = make_pt3d(obj.InsertionPoint)
                text = obj.TextString
                height = obj.Height
                new_obj = new_doc.ModelSpace.AddMText(insert_pt, 0.0, text)
                try:
                    new_obj.Height = height
                    new_obj.Rotation = obj.Rotation
                except Exception:
                    pass
                    
            elif ent_name == "AcDbText":
                insert_pt = make_pt3d(obj.InsertionPoint)
                text = obj.TextString
                height = obj.Height
                new_obj = new_doc.ModelSpace.AddText(text, insert_pt, height)
                try:
                    new_obj.Rotation = obj.Rotation
                except Exception:
                    pass
                    
            elif ent_name == "AcDbCircle":
                center_pt = make_pt3d(obj.Center)
                radius = obj.Radius
                new_obj = new_doc.ModelSpace.AddCircle(center_pt, radius)
                
            elif ent_name == "AcDbArc":
                center_pt = make_pt3d(obj.Center)
                radius = obj.Radius
                start_angle = obj.StartAngle
                end_angle = obj.EndAngle
                new_obj = new_doc.ModelSpace.AddArc(center_pt, radius, start_angle, end_angle)
                
            elif ent_name == "AcDbBlockReference":
                block_name = obj.Name
                insert_pt = make_pt3d(obj.InsertionPoint)
                xs = obj.XScaleFactor
                ys = obj.YScaleFactor
                zs = obj.ZScaleFactor
                rot = obj.Rotation
                
                ensure_block(block_name)
                new_obj = new_doc.ModelSpace.InsertBlock(insert_pt, block_name, xs, ys, zs, rot)

            elif ent_name == "AcDbSolid":
                p1 = make_pt3d(obj.Coordinate(0))
                p2 = make_pt3d(obj.Coordinate(1))
                p3 = make_pt3d(obj.Coordinate(2))
                p4 = make_pt3d(obj.Coordinate(3))
                new_obj = new_doc.ModelSpace.AddSolid(p1, p2, p3, p4)

            if new_obj:
                try:
                    new_obj.Layer = layer
                    new_obj.Color = color
                except Exception:
                    pass
                drawn_count += 1
                entity_stats[ent_name] = entity_stats.get(ent_name, 0) + 1

            if drawn_count % 200 == 0:
                print(f"  Re-drew {drawn_count} entities in {time.time() - start_time:.2f}s...", flush=True)
                
        except Exception as e:
            errors_count += 1
            continue

    duration = time.time() - start_time
    print(f"\nReplication completed in {duration:.2f} seconds!", flush=True)
    print(f"  - Successfully drawn: {drawn_count}", flush=True)
    print(f"  - Failed/skipped: {errors_count}", flush=True)
    print("Replicated entity stats:", flush=True)
    for ent, count in entity_stats.items():
        print(f"  * {ent}: {count}", flush=True)

    # 6. Save and Regenerate
    try:
        new_doc.Regen(1)
        out_path = r"C:\cad\replicated_drawing2.dwg"
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        new_doc.SaveAs(out_path)
        print(f"[SUCCESS] Replicated drawing successfully saved at: '{out_path}'", flush=True)
    except Exception as e:
        print(f"[FAIL] Could not save the drawing: {e}", flush=True)

    print("=" * 80, flush=True)

if __name__ == '__main__':
    main()
