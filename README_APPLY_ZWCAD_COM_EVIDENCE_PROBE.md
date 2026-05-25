# Apply ZWCAD COM Evidence Probe

## Instructions
1. This package introduces a safe COM Evidence Probe (`src/analysis/zwcad_com_evidence_probe.py`).
2. It includes a worker wrapper and a CLI interface.
3. The probe will NOT mutate any documents, execute commands, or save files. It merely attaches to the ZWCAD application.
4. Integrate by merging the CLI module into `src/main.py`.

## Running the Probe
Run the command below in safety/attach-only mode:
```powershell
python -X utf8 -m src.main hscad-zwcad-com-evidence-probe --out-dir outputs\zwcad_com_evidence_probe
```
