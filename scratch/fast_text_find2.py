import win32com.client

def main():
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    ms = app.ActiveDocument.ModelSpace
    
    for i in range(ms.Count):
        try:
            obj = ms.Item(i)
            name = obj.ObjectName
            if name == "AcDbBlockReference":
                if obj.HasAttributes:
                    for att in obj.GetAttributes():
                        if "단면도" in att.TextString:
                            print(f"FOUND BLOCK TEXT: {att.TextString} at {obj.InsertionPoint}")
            elif name in ("AcDbText", "AcDbMText"):
                if "단면도" in obj.TextString:
                    print(f"FOUND TEXT: {obj.TextString} at {obj.InsertionPoint}")
        except Exception:
            pass
            
if __name__ == "__main__":
    main()
