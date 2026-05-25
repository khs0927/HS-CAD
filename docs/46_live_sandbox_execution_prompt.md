# Validation prompt for Live Sandbox Delta Extraction

Repository:
khs0927/HS-CAD

Branch:
exp/reverse-engineering-delta-extractor

Goal:
Validate that `xicad-sandbox-extract` can successfully connect to ZWCAD, duplicate a blank template DWG, execute a XiCAD command, take snapshots, and save the resulting Delta signature.

Rules:
- Requires a live ZWCAD instance to be open.
- Requires a blank DWG template path provided by the user.
- If live ZWCAD cannot handle the COM request, provide a mock or skip gracefully, but ensure the architecture remains valid.

Commands:

git fetch origin exp/reverse-engineering-delta-extractor
git switch exp/reverse-engineering-delta-extractor

# Replace 'C:/path/to/blank.dwg' with an actual blank DWG file
python -X utf8 -m src.main xicad-sandbox-extract --template-dwg "C:/path/to/blank.dwg" --command-hint "WAL" --input-sequence "WAL\n0,0\n1000,0\n\n" --delay 2.0

Confirm:
- `xicad-sandbox-extract` successfully connects to COM.
- A sandbox copy is created in `outputs/xicad_signatures/`.
- `outputs/xicad_signatures/WAL_signature.json` is generated.
- The JSON contains added entities representing the wall geometry.

Report:
- Branch/commit tested
- CLI execution result
- Artifact verification result
- Failures or COM timeouts
