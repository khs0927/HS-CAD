import sys, os, json

# Ensure project src is in path
sys.path.insert(0, os.path.abspath('src'))

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter

# Connect to ZWCAD and get the active document (the one currently opened by the user)
adapter = ZWCADCOMAdapter(visible=False)
adapter.connect()
# If a document is already active, just get it; otherwise, use the currently opened one
active_doc = adapter.get_active_document()
print('Active document name:', active_doc.Name)

# Scan modelspace once – this returns a list of dicts with keys like 'layer', 'object_name', 'text', etc.
objects = adapter.scan_modelspace()

# Helper to collect text strings from a specific layer substring (case‑insensitive)
def collect_texts(substring):
    txts = []
    for obj in objects:
        layer = str(obj.get('layer') or '')
        if substring.lower() in layer.lower():
            # Text may be in 'text' key (MText) or 'text_string' (standard Text)
            txt = obj.get('text') or obj.get('text_string')
            if isinstance(txt, str):
                txts.append(txt)
    return txts

# 1) Get building overview text (layer containing "BUILDING" – adjust if your project uses a different name)
building_texts = collect_texts('building')
if not building_texts:
    print('WARNING: No text found on a layer containing "building". Using empty string.')
building_overview = '\n'.join(building_texts)
print('--- Building overview (joined) ---')
print(building_overview[:500])  # show first part for verification

# 2) Replace texts on landscape layers (layers containing "landscape")
replaced = 0
for obj in objects:
    layer = str(obj.get('layer') or '')
    if 'landscape' in layer.lower():
        # Only handle actual text entities
        obj_name = str(obj.get('object_name') or '').lower()
        if 'text' in obj_name:
            # Use the COM object via adapter._iter_modelspace() – easier to modify directly
            # We'll locate the same entity by its handle
            handle = obj.get('handle')
            if not handle:
                continue
            # Find the COM object with that handle
            for ent in adapter._iter_modelspace():
                if str(adapter._safe_get(ent, 'Handle')) == str(handle):
                    try:
                        ent.TextString = building_overview
                        replaced += 1
                    except Exception as e:
                        print(f'Failed to replace text on handle {handle}: {e}')
                    break

print(f'Total landscape text objects replaced: {replaced}')

# 3) Insert a TODO note on a dedicated layer (create it if missing)
TODO_LAYER = 'A-LANDSCAPE_TODO'
TODO_TEXT = 'TODO: 조경 상세 설계(식물 배치·조명·석재·조경 설비) 내용 추가'
# Insert at origin (0,0,0) – user can move later
try:
    adapter.create_text(TODO_TEXT, [0, 0, 0], height=150.0, layer=TODO_LAYER, color=4)
    print('Inserted TODO text.')
except Exception as e:
    print('Failed to insert TODO text:', e)

# 4) Save a copy – keep original untouched
output_path = os.path.join(os.path.dirname(active_doc.Path), 'modified_' + os.path.basename(active_doc.Path))
adapter.save_as(output_path)
print('Saved modified drawing to:', output_path)
