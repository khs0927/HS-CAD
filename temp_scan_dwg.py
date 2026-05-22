import sys, json, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
adapter = ZWCADCOMAdapter(visible=True)
adapter.connect()
# list layers
layers = adapter.list_layers()
print('=== LAYERS ===')
for l in layers:
    print(l)
# scan modelspace texts
objects = adapter.scan_modelspace()
text_objects = [o for o in objects if 'text' in str(o.get('object_name','')).lower()]
print('=== TEXT OBJECTS (first 30) ===')
for t in text_objects[:30]:
    print(t.get('layer'), '|', t.get('text', '')[:100])