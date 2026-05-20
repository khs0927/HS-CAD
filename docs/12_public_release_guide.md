# Public Release Guide

The internal package can include `vendor/xicad`, but public GitHub distribution should normally exclude it.

## Create public package

```powershell
python tools/prepare_public_release.py --out "../zwcad-ai-modifier-public"
```

The generated release excludes:

- `vendor/xicad/`
- `outputs/`
- `backups/`
- runtime `generated/` artifacts
- DWG/DXF files
- caches

Users should install XiCAD separately and configure the local path in `config/xicad_profile.example.yaml`.
