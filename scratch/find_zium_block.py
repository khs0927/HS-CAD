# -*- coding: utf-8 -*-
import win32com.client
import sys

def find_zium_block():
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
    except:
        sys.exit(1)
        
    print("Available Blocks:")
    for i in range(doc.Blocks.Count):
        b = doc.Blocks.Item(i)
        name = b.Name.upper()
        if not name.startswith("*"):
            if any(k in name for k in ["ZIUM", "SHEET", "TITLE", "도곽", "도각", "FORM", "A3", "A1", "FRAME"]):
                print(f" - {b.Name}")

if __name__ == "__main__":
    find_zium_block()
