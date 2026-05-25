import json
import logging
from pathlib import Path

import click

from src.analysis.final_live_runner import FinalLiveRunner
from src.app.cli import app

logger = logging.getLogger(__name__)

@app.command("zwcad-copy-scan-validate")
@click.option("--original-dwg", required=True, help="Original DWG path.")
@click.option("--working-copy-dwg", required=True, help="Copied DWG path.")
@click.option("--out-dir", required=True, help="Output directory.")
def zwcad_copy_scan_validate_cmd(original_dwg: str, working_copy_dwg: str, out_dir: str):
    """Copied DWG scan validation."""
    logger.info("Running ZWCAD copy scan validation...")
    runner = FinalLiveRunner()
    result = runner.zwcad_copy_scan_validate(original_dwg, working_copy_dwg, out_dir)
    
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    res_path = out_path / "LOCAL_01_COPIED_DWG_SCAN_RESULT.json"
    
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Result written to {res_path}")

@app.command("zwcad-copy-saveas-validate")
@click.option("--original-dwg", required=True, help="Original DWG path.")
@click.option("--working-copy-dwg", required=True, help="Copied DWG path.")
@click.option("--save-as-target", required=True, help="SaveAs target path.")
@click.option("--out-dir", required=True, help="Output directory.")
@click.option("--overwrite-copy", is_flag=True, help="Allow overwrite.")
def zwcad_copy_saveas_validate_cmd(original_dwg: str, working_copy_dwg: str, save_as_target: str, out_dir: str, overwrite_copy: bool):
    """Copied DWG SaveAs validation."""
    logger.info("Running ZWCAD copy SaveAs validation...")
    runner = FinalLiveRunner()
    result = runner.zwcad_copy_saveas_validate(original_dwg, working_copy_dwg, save_as_target, out_dir, overwrite_copy)
    
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    res_path = out_path / "LOCAL_02_COPIED_DWG_SAVEAS_RESULT.json"
    
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Result written to {res_path}")

@app.command("xicad-policy-candidates")
@click.option("--xicad-root", required=True, help="XiCAD root path.")
@click.option("--out-dir", required=True, help="Output directory.")
def xicad_policy_candidates_cmd(xicad_root: str, out_dir: str):
    """C:/xicad allowlist policy validation."""
    logger.info("Running XiCAD policy candidate validation...")
    runner = FinalLiveRunner()
    result = runner.xicad_policy_candidates(xicad_root, out_dir)
    
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    res_path = out_path / "LOCAL_03_XICAD_POLICY_CANDIDATES_RESULT.json"
    
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Result written to {res_path}")
