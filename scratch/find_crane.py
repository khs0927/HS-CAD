import win32com.client

def main():
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    ms = app.ActiveDocument.ModelSpace
    
    for i in range(ms.Count):
        try:
            obj = ms.Item(i)
            name = obj.ObjectName
            if name in ("AcDbText", "AcDbMText"):
                if "CRANE" in obj.TextString:
                    print(f"FOUND TEXT: {obj.TextString} at {obj.InsertionPoint}")
        except Exception:
            pass
            
if __name__ == "__main__":
    main()
