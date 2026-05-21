# 28. XiCAD Rule Engine v2

## Purpose

XiCAD Rule Engine v2 extracts parseable drafting knowledge from a local XiCAD installation and turns it into structured constraints for HS-CAD.

It does **not** attempt to decrypt protected XiCAD LISP binaries.

## Supported sources

- `xiLib/xiShortkey.key`: alias -> LISP function -> Korean description mapping
- `_ZWCad/zwcad.pgp`: CAD command alias table
- `Lisp/*.dat`: steel section/specification tables
- `Lib/**/*.dwg`: block library catalog
- `Lisp/*.des`: protected LISP detection and safe isolation
- Optional: `xiDrawWall.txt`, `xiBlkLayerSet.txt`, `xiConfig.cfg`

## Main API

```python
from src.integrations.xicad_rule_engine import XiCadRuleEngine

engine = XiCadRuleEngine("C:/xicad")
rules = engine.load_all()
summary = engine.summarize(rules)
prompt = engine.generate_ai_drafting_prompt(rules)
engine.export_rules_to_json("outputs/xicad_extracted_rules.json", rules)
```

## CLI

```powershell
python -m src.integrations.xicad_rule_engine --xicad-root C:\xicad --out-json outputs/xicad_extracted_rules.json --out-prompt outputs/xicad_drafting_prompt.md
```

## Integrity audit

```powershell
python tests/verify_p0_p1_p2_integrity.py --xicad-root C:\xicad --out outputs/xicad_integrity_report.json
```

## Safety notes

- `.des`, `.fas`, `.zelx` style protected/compiled assets are not decoded.
- The engine only reads parseable metadata/configuration/catalog files.
- Generated outputs under `outputs/` are runtime artifacts and should not be committed.
