# Codex Prompt: HS-CAD Main-Code Overlay v2

Apply `hs_cad_main_code_overlay_v2.zip` after v1 validation. Keep it review-only.

Goals:
1. Use runtime DXF fixture generation instead of committing `tests/fixtures/minimal_floorplan.dxf`.
2. Validate `python -m hscad.app.cli_main_code`.
3. Dry-run and inspect `scripts/register_main_code_cli.py` before applying it to `src/main.py`.
4. Strengthen DXF writer via optional `ezdxf` with fallback ASCII writer.

Do not execute CAD, ZWCAD COM, SendCommand or XiCAD aliases. Do not mutate original DWG/DXF files. Do not commit outputs, zips, caches or runtime CAD artifacts.
