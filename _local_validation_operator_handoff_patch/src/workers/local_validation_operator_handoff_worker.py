from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.local_validation_operator_handoff import write_operator_handoff_outputs


def run(
    *,
    out_dir: str | Path = "outputs/local_validation_operator_handoff",
    original_dwg: str = "C:/cad/test/original.dwg",
    working_copy_dwg: str = "C:/cad/test_work/copy.dwg",
    save_as_target: str = "C:/cad/test_work/result.dwg",
    xicad_root: str = "C:/xicad",
    **_: Any,
) -> dict[str, Any]:
    """Generate manual local validation operator handoff artifacts. Does not run CAD."""

    return write_operator_handoff_outputs(
        out_dir=out_dir,
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
        xicad_root=xicad_root,
    )


def run_worker(**kwargs: Any) -> dict[str, Any]:
    return run(**kwargs)
