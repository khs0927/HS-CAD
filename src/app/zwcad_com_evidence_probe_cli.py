import json
import logging
from pathlib import Path
import typer

from src.app.cli import app
from src.analysis.zwcad_com_evidence_probe import ZWCADCOMEvidenceProbe
from src.app.logger import console

logger = logging.getLogger(__name__)

@app.command("hscad-zwcad-com-evidence-probe")
def zwcad_com_evidence_probe(
    out_dir: str = typer.Option(..., "--out-dir", help="Output directory."),
    attach_only: bool = typer.Option(True, "--attach-only/--no-attach-only", help="Attach to running ZWCAD only."),
    start_if_needed: bool = typer.Option(False, "--start-if-needed", is_flag=True, help="Start ZWCAD if not running.")
):
    """ZWCAD COM evidence collection probe. Does not execute CAD commands."""
    logger.info("Running ZWCAD COM evidence probe...")
    probe = ZWCADCOMEvidenceProbe()
    result = probe.collect_evidence(attach_only=attach_only, start_if_needed=start_if_needed)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    json_path = out_path / "ZWCAD_COM_EVIDENCE_PROBE.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    md_path = out_path / "ZWCAD_COM_EVIDENCE_PROBE.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# ZWCAD COM Evidence Probe Result\n\n")
        f.write(f"- Status: {result.get('status')}\n")
        f.write(f"- Connected: {result.get('connected')}\n")
        f.write(f"- Active ProgID: {result.get('active_progid')}\n")

    candidates_path = out_path / "ZWCAD_COM_PROGID_CANDIDATES.json"
    with open(candidates_path, "w", encoding="utf-8") as f:
        json.dump(result.get("candidate_progids", []), f, indent=2)

    console.print(f"[bold green]Probe completed. Status: {result.get('status')}[/bold green]")
    logger.info(f"Generated {json_path}")
