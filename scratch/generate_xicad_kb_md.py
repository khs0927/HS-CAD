import json
from pathlib import Path

d = json.load(open('outputs/xicad_deep_analysis_dump.json', encoding='utf-8'))
stats = d['statistics']
know = d['knowledge']

lines = []
lines.append('# XiCAD Deep Knowledge Base')
lines.append('This document contains a highly detailed breakdown of the internal structure and domain rules extracted from `C:/xicad`.')
lines.append('It is intended to provide HS-CAD agents with full visibility into the assets and rules available.')
lines.append('')
lines.append('## 1. Global Statistics')
for k, v in stats.items():
    if v > 0:
        lines.append(f'- **{k}**: {v}')
lines.append('')

lines.append('## 2. Text Presets & Leaders')
lines.append('### Auto Leaders')
for al in know.get('auto_leaders', []):
    lines.append(f'- `{al}`')
lines.append('### Common Texts')
for ct in know.get('common_texts', []):
    lines.append(f'- `{ct}`')
lines.append('### Text Boxes')
for tb in know.get('text_boxes', []):
    lines.append(f'- `{tb}`')
lines.append('')

lines.append('## 3. Configuration & System Files')
for ini, content in know.get('ini_configs', {}).items():
    lines.append(f'### `{ini}`')
    lines.append('```ini')
    lines.append(content[:200] + '... (truncated)')
    lines.append('```')
lines.append('')

lines.append('## 4. Slide Libraries (.slb)')
lines.append('Contains thumbnail UI catalogs for ZWCAD/AutoCAD dialogs.')
for slb in know.get('slb_libraries', []):
    lines.append(f'- `{slb["path"]}` ({slb["size_kb"]} KB)')
lines.append('')

lines.append('## 5. Lisp Assets')
lines.append('Total compiled components (.fas, .des, .zelx): ~84')
lines.append('Readable Lisp scripts:')
for lsp in know.get('lisp_files', []):
    lines.append(f'- `{lsp}`')

Path('docs/XICAD_KNOWLEDGE_BASE.md').parent.mkdir(parents=True, exist_ok=True)
Path('docs/XICAD_KNOWLEDGE_BASE.md').write_text('\n'.join(lines), encoding='utf-8')
print('Wrote docs/XICAD_KNOWLEDGE_BASE.md')
