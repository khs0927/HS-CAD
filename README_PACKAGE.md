# Internal Package Notes

This repository can be used as an internal Windows + ZWCAD + XiCAD automation package.

## Vendor/XiCAD

- Do not modify `vendor/xicad`.
- Do not edit XiCAD compiled/resource files such as `.fas`, `.zelx`, `.zrx`, or `.des`.
- Confirm redistribution rights before sharing any package that includes XiCAD files.
- Public GitHub releases should exclude `vendor/xicad`.

## Public Release

Use:

```powershell
python tools/prepare_public_release.py --out "../release_public"
```

For a preview:

```powershell
python tools/prepare_public_release.py --out "../release_public" --dry-run
```

The script excludes vendor files, generated runtime artifacts, outputs, and backups.
