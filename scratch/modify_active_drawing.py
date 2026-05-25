from __future__ import annotations
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.encoding import ensure_utf8_stdio
ensure_utf8_stdio()

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter

def main():
    try:
        adapter = ZWCADCOMAdapter(visible=True)
        adapter.connect()
        
        if adapter.app is None:
            print("Failed to connect to ZWCAD app.")
            return
            
        doc = adapter.app.ActiveDocument
        print(f"Modifying Active Document: {doc.Name}")
        
        # We will perform live replacements on ModelSpace text entities
        replacements = [
            # (Find string, Replace string)
            ("강서구 명지동 3259-6", "김해시 화목동 698-14"),
            ("상가주택 신축공사", "신진유압 신축공사"),
            ("강서구 명지동", "김해시 화목동"),
            ("3259-6", "698-14"),
            ("상가주택", "신진유압")
        ]
        
        total_changed = 0
        
        # Iterate over all entities in ModelSpace
        for obj in doc.ModelSpace:
            try:
                object_name = str(getattr(obj, "ObjectName", "") or "").lower()
                if "text" not in object_name:
                    continue
                    
                current_text = getattr(obj, "TextString", None)
                if not current_text or not isinstance(current_text, str):
                    continue
                    
                new_text = current_text
                changed = False
                for find_str, replace_str in replacements:
                    if find_str in new_text:
                        new_text = new_text.replace(find_str, replace_str)
                        changed = True
                        
                if changed:
                    obj.TextString = new_text
                    print(f"Replaced text: '{current_text}' -> '{new_text}' on layer '{getattr(obj, 'Layer', '')}'")
                    total_changed += 1
            except Exception as e:
                # Silently ignore COM access errors for non-matching entities
                continue
                
        if total_changed > 0:
            # Refresh drawing screen to show changes
            try:
                doc.Regen(1)
                print("Regenerated screen successfully.")
            except Exception:
                pass
            print(f"\nSuccessfully replaced {total_changed} text occurrences!")
        else:
            print("\nNo matching text elements found to replace.")
            
    except Exception as e:
        print(f"Error during modification: {e}")

if __name__ == "__main__":
    main()
