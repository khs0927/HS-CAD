import win32com.client

def main():
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    ms = app.ActiveDocument.ModelSpace
    count = ms.Count
    print(f"Total objects: {count}")
    
    for i in range(count):
        try:
            obj = ms.Item(i)
            name = obj.ObjectName
            if name in ("AcDbText", "AcDbMText"):
                txt = obj.TextString
                if "종단면도" in txt or "횡단면도" in txt:
                    print(f"FOUND: {txt} at {obj.InsertionPoint}")
        except Exception:
            pass
            
if __name__ == "__main__":
    main()
