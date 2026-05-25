"""Review-only command wrapper for the main-code pipeline.

Example:
    python -m hscad.app.cli_main_code --input sample.dxf --out outputs/main_code
"""
from __future__ import annotations

from hscad.pipelines.main_code_pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())
