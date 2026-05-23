import win32com.client
import sys

def find_section_coordinates():
    try:
        app = win32com.client.GetActiveObject("ZWCAD.Application")
        doc = app.ActiveDocument
        ms = doc.ModelSpace
        print(f"Scanning {ms.Count} objects...")
        
        found = False
        for i in range(ms.Count):
            obj = ms.Item(i)
            if hasattr(obj, 'TextString'):
                txt = obj.TextString
                if "종단면도-1" in txt or "종단면도-2" in txt or "횡단면도" in txt:
                    ins = obj.InsertionPoint
                    print(f"FOUND: '{txt}' at X:{ins[0]:.2f}, Y:{ins[1]:.2f}")
                    found = True
        
        if not found:
            print("Could not find text '종단면도-1', '종단면도-2', or '횡단면도'")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_section_coordinates()
