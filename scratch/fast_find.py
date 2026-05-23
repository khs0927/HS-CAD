import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter

def main():
    adapter = ZWCADCOMAdapter()
    adapter.connect()
    print("Scanning active doc...")
    objs = adapter.scan_modelspace()
    
    for obj in objs:
        if obj.get('entity_type') in ('TEXT', 'MTEXT'):
            txt = str(obj.get('text', ''))
            if '종단면도' in txt or '횡단면도' in txt:
                print(f"FOUND SECTION: {txt}")
                print(f"Coordinates: {obj.get('insert')}")

if __name__ == "__main__":
    main()
