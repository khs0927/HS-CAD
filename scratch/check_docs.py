import win32com.client
import sys

try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    print(f"Connected to: {app.Name} {app.Version}")
    print(f"Documents count: {app.Documents.Count}")
    if app.Documents.Count > 0:
        for i in range(app.Documents.Count):
            doc = app.Documents.Item(i)
            print(f"Doc {i}: {doc.Name} (Path: {doc.FullName})")
        active_doc = app.ActiveDocument
        print(f"Active Document: {active_doc.Name}")
    else:
        print("No documents open.")
except Exception as e:
    print(f"Error: {e}")
