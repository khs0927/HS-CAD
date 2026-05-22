import sys, os
sys.path.insert(0, os.path.abspath('src'))

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.scanners.text_scanner import extract_texts

adapter = ZWCADCOMAdapter(visible=False)
adapter.connect()
doc = adapter.get_active_document()
print('Active doc:', doc.Name)

# Get building overview texts (layer containing 'building')
building_texts = extract_texts(adapter.scan_modelspace())
# filter by layer containing building
building_texts = [t for t in building_texts if 'building' in str(t.get('layer','')).lower()]
if not building_texts:
    print('WARNING: No building overview texts found')
building_overview = '\n'.join(t.get('text','') for t in building_texts)
print('Building overview length:', len(building_overview))

# Get landscape text objects (layer containing 'landscape')
all_texts = extract_texts(adapter.scan_modelspace())
landscape_texts = [t for t in all_texts if 'landscape' in str(t.get('layer','')).lower()]
print('Found', len(landscape_texts), 'landscape text objects')

# Replace each landscape text with building_overview
replaced = 0
for txt_obj in landscape_texts:
    handle = txt_obj.get('handle')
    if not handle:
        continue
    # find COM object by handle and replace TextString
    for ent in adapter._iter_modelspace():
        if str(adapter._safe_get(ent, 'Handle')) == str(handle):
            try:
                ent.TextString = building_overview
                replaced += 1
            except Exception as e:
                print(f'Failed replace on handle {handle}: {e}')
            break
print('Replaced', replaced, 'landscape text objects')

# Insert TODO note
TODO_LAYER = 'A-LANDSCAPE_TODO'
TODO_TEXT = 'TODO: 조경 상세 설계(식물 배치·조명·석재·조경 설비) 내용 추가'
try:
    adapter.create_text(TODO_TEXT, [0,0,0], height=150.0, layer=TODO_LAYER, color=4)
    print('Inserted TODO text')
except Exception as e:
    print('Failed to insert TODO:', e)

# Save copy
output_path = os.path.join(os.path.dirname(doc.Path), 'modified_' + os.path.basename(doc.Path))
adapter.save_as(output_path)
print('Saved modified drawing to:', output_path)