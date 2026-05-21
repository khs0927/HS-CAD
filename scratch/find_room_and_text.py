import win32com.client

try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    ms = doc.ModelSpace
    
    print("Searching for '테스트실' and '석고보드'...")
    
    test_rooms = []
    gypsum_texts = []
    
    for i in range(ms.Count):
        obj = ms.Item(i)
        obj_name = obj.ObjectName.lower()
        
        if "text" in obj_name:
            text_str = obj.TextString
            insert = list(obj.InsertionPoint)
            
            if "테스트실" in text_str:
                test_rooms.append({'text': text_str, 'pos': insert, 'handle': obj.Handle})
                print(f"Found room: '{text_str}' at {insert}")
            
            if "석고보드" in text_str:
                gypsum_texts.append({'text': text_str, 'pos': insert, 'handle': obj.Handle})
                print(f"Found gypsum text: '{text_str}' at {insert}")
                
    if not test_rooms:
        print("No '테스트실' found.")
    if not gypsum_texts:
        print("No '석고보드' found.")

except Exception as e:
    print(f"Error: {e}")
