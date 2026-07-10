from __future__ import annotations

from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.xicad_automation.catalog import AutomationCatalog
from src.xicad_automation.contracts import PromptContract


@app.command("xicad-contract-bootstrap-all")
def xicad_contract_bootstrap_all(
    xicad_root: Path = typer.Option(..., "--xicad-root"),
    out_dir: Path = typer.Option(Path("config/xicad_contracts"), "--out-dir"),
    overwrite: bool = typer.Option(False, "--overwrite"),
):
    """Create one unverified prompt-contract template for every installed XiCAD alias."""
    rows = AutomationCatalog.from_xicad_root(xicad_root).describe()
    out_dir.mkdir(parents=True, exist_ok=True)
    created = 0
    skipped = 0
    for row in rows:
        path = out_dir / f"{row['alias']}.json"
        if path.exists() and not overwrite:
            skipped += 1
            continue
        contract = PromptContract(
            alias=row["alias"],
            argument_templates=[],
            verified=False,
            notes=(
                f"Generated from {row['source']}. Observe the exact prompt sequence on a disposable DWG, "
                "add argument_templates, validate UNDO and side effects, then set verified=true."
            ),
        )
        path.write_text(contract.model_dump_json(indent=2), encoding="utf-8")
        created += 1
    console.print({"discovered": len(rows), "created": created, "skipped": skipped, "out_dir": str(out_dir)})
    success("XiCAD all-command contract bootstrap completed")
