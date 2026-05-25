from __future__ import annotations
from pathlib import Path
from typing import Any
from src.analysis.phase3_real_data_binding import write_phase3_real_data_binding_outputs

def run(workspace: str | Path = "outputs/webhard_batch_100", *, out_dir: str | Path | None = None, **_: Any) -> dict[str, Any]:
    return write_phase3_real_data_binding_outputs(workspace, out_dir=out_dir)

def run_worker(workspace: str | Path = "outputs/webhard_batch_100", *, out_dir: str | Path | None = None, **kwargs: Any) -> dict[str, Any]:
    return run(workspace=workspace, out_dir=out_dir, **kwargs)

def main(workspace: str | Path = "outputs/webhard_batch_100", *, out_dir: str | Path | None = None, **kwargs: Any) -> dict[str, Any]:
    return run(workspace=workspace, out_dir=out_dir, **kwargs)
