# -*- coding: utf-8 -*-
import win32com.client
import pythoncom
import json

def get_selection_set(doc, name):
    try:
        doc.SelectionSets.Item(name).Delete()
    except:
        pass
    return doc.SelectionSets.Add(name)

def main():
    try:
        zwcad = win32com.client.Dispatch("ZWCAD.Application")
        doc = zwcad.ActiveDocument
        
        print(f"Active Document: {doc.Name}")
        
        # 1. 치수(Dimension) 스캔
        ss_dims = get_selection_set(doc, "SS_DIMS")
        filter_type = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, [0])
        filter_data = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, ["DIMENSION"])
        ss_dims.Select(5, filter_type, filter_data) # 5 = acSelectionSetAll
        
        dims_data = []
        for i in range(min(ss_dims.Count, 200)):
            obj = ss_dims.Item(i)
            txt = getattr(obj, "TextOverride", "") or getattr(obj, "Measurement", 0.0)
            dims_data.append(str(txt))
        
        # 2. 문자(Text, MText) 스캔
        ss_texts = get_selection_set(doc, "SS_TEXTS")
        f_type_txt = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, [0])
        f_data_txt = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, ["*TEXT"])
        ss_texts.Select(5, f_type_txt, f_data_txt)
        
        texts_data = []
        for i in range(min(ss_texts.Count, 100)):
            obj = ss_texts.Item(i)
            txt = getattr(obj, "TextString", "")
            texts_data.append(txt)
            
        print(f"\n--- FAST SCAN RESULT ---")
        print(f"Total Dimensions: {ss_dims.Count}")
        print(f"Total Texts: {ss_texts.Count}")
        print("Sample Dimensions:", dims_data[:10])
        
        # 특정 치수가 있다면 (예: 300, 150, 400 등), 이를 통해 기둥 규격을 유추
        h_sizes = [d for d in dims_data if str(d).replace('.0','').isdigit() and int(float(d)) in [100, 125, 150, 175, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800]]
        print("\nPotential Steel/Column Sizes from Dims:", list(set(h_sizes)))
        
    except Exception as e:
        print(f"Error scanning ZWCAD: {e}")

if __name__ == "__main__":
    main()
