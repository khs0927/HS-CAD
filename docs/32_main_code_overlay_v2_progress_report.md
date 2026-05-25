# HS-CAD Main-Code Overlay v2 Progress Report

This overlay reduces the remaining risks identified after `hs_cad_main_code_overlay_v1.zip` validation.

## Adds

- Runtime DXF fixture factory: `tests/fixtures/minimal_floorplan_factory.py`
- Review-only CLI wrapper: `python -m hscad.app.cli_main_code`
- Conservative optional `src/main.py` patch script: `scripts/register_main_code_cli.py`
- Improved DXF adapter/writer with optional `ezdxf` writer and fallback ASCII DXF writer
- Tests for fixture generation, CLI wrapper, patch dry-run and pipeline smoke

## Safety

No live CAD execution. No AutoCAD/ZWCAD COM. No SendCommand. No XiCAD alias execution. No original DWG mutation.
