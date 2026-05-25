from __future__ import annotations
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter

def main():
    try:
        adapter = ZWCADCOMAdapter(visible=True)
        adapter.connect()
        
        if adapter.app is None:
            print("Failed to connect to ZWCAD app.")
            return
            
        doc = adapter.app.ActiveDocument
        print(f"Active Document Name: {doc.Name}")
        print(f"Active Document Full Path: {doc.FullName}")
        
        # Count some basic elements in ModelSpace
        modelspace = doc.ModelSpace
        count = modelspace.Count
        print(f"Number of entities in ModelSpace: {count}")
        
    except Exception as e:
        print(f"Error connecting to active ZWCAD: {e}")

if __name__ == "__main__":
    main()
