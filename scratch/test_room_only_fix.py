import win32com.client
import math

def get_dist(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

try:
    app = win32com.client.GetActiveObject("ZWCAD.Application")
    doc = app.ActiveDocument
    ms = doc.ModelSpace
    
    print("Redoing changes specifically for '테스트실'...")
    
    test_room_coords = []
    texts_to_check = []
    
    # First pass: find room locations and all relevant text
    for i in range(ms.Count):
        obj = ms.Item(i)
        if "text" in obj.ObjectName.lower():
            text = obj.TextString
            pos = list(obj.InsertionPoint)
            handle = obj.Handle
            
            if "테스트실" in text:
                test_room_coords.append(pos)
                print(f"Room found: '{text}' at {pos}")
            
            if any(k in text for k in ["석고보드", "방음 판넬"]):
                texts_to_check.append({'obj': obj, 'text': text, 'pos': pos, 'handle': handle})

    # Second pass: Apply logic
    updated_count = 0
    reverted_count = 0
    
    for item in texts_to_check:
        obj = item['obj']
        text = item['text']
        pos = item['pos']
        
        # Check proximity to any "테스트실" (within 10m / 10000 units assuming mm)
        is_near_test_room = any(get_dist(pos, r_pos) < 10000 for r_pos in test_room_coords)
        
        if is_near_test_room:
            # Upgrade to premium soundproof spec for Test Room
            if "방음 판넬" not in text:
                new_text = text.replace("석고보드", "차음방음 판넬")
                obj.TextString = new_text
                print(f"Applied to Test Room area [{item['handle']}]: '{text}' -> '{new_text}'")
                updated_count += 1
            else:
                # Already changed, just polish it
                new_text = text.replace("방음 판넬", "차음방음 판넬")
                if new_text != text:
                    obj.TextString = new_text
                    print(f"Polished Test Room area [{item['handle']}]: '{text}' -> '{new_text}'")
                    updated_count += 1
        else:
            # Revert if it's NOT near a test room but has "방음 판넬"
            if "방음 판넬" in text:
                new_text = text.replace("방음 판넬", "석고보드").replace("차음방음 판넬", "석고보드")
                obj.TextString = new_text
                print(f"Reverted non-test area [{item['handle']}]: '{text}' -> '{new_text}'")
                reverted_count += 1

    doc.Regen(1)
    print(f"Done. Updated: {updated_count}, Reverted: {reverted_count}")

except Exception as e:
    print(f"Error: {e}")
