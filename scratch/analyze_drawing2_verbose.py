# -*- coding: utf-8 -*-
"""
Verbose, ultra-defensive audit of Drawing2.dwg to trace freezes on individual entities.
"""
import sys

def main():
    print("=" * 80, flush=True)
    print("Drawing2.dwg Verbose Freeze-Trace Audit", flush=True)
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

    doc2 = None
    for doc in app.Documents:
        if doc.Name.lower() == "drawing2.dwg":
            doc2 = doc
            break

    if not doc2:
        print("[FAIL] Drawing2.dwg is not open.", flush=True)
        return

    print(f"[SUCCESS] Connected to active document: {doc2.Name}", flush=True)

    print("Starting ModelSpace verbose trace...", flush=True)
    for i, obj in enumerate(doc2.ModelSpace):
        try:
            print(f"Index {i}: Class={type(obj).__name__}", end="", flush=True)
            
            # 1. ObjectName
            obj_name = "N/A"
            try:
                obj_name = obj.ObjectName
                print(f" | ObjectName={obj_name}", end="", flush=True)
            except Exception as e:
                print(f" | ObjectName_err={type(e).__name__}", end="", flush=True)

            # 2. EntityName
            ent_name = "N/A"
            try:
                ent_name = obj.EntityName
                print(f" | EntityName={ent_name}", end="", flush=True)
            except Exception as e:
                print(f" | EntityName_err={type(e).__name__}", end="", flush=True)

            # 3. Layer
            layer = "N/A"
            try:
                layer = obj.Layer
                print(f" | Layer={layer}", end="", flush=True)
            except Exception as e:
                print(f" | Layer_err={type(e).__name__}", end="", flush=True)

            # 4. Color
            color = "N/A"
            try:
                color = obj.Color
                print(f" | Color={color}", end="", flush=True)
            except Exception as e:
                print(f" | Color_err={type(e).__name__}", end="", flush=True)

            print(" [OK]", flush=True)
            
        except Exception as e:
            print(f" | Outer_err={type(e).__name__}", flush=True)

    print("Trace completed successfully!", flush=True)
    print("=" * 80, flush=True)

if __name__ == '__main__':
    main()
