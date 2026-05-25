"""
Review-only CLI registry for HS-CAD main-code/evidence-bridge pipelines.

This module intentionally registers *review-only* commands. It must not call
AutoCAD, ZWCAD COM, SendCommand, XiCAD alias execution, or mutate original DWG
files. The commands delegate to existing pipeline modules that write analysis
artifacts under an explicit output directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional
import importlib


COMMAND_MAIN_CODE = "hscad-main-code-pipeline"
COMMAND_EVIDENCE_BRIDGE = "hscad-evidence-bridge"


def _load_callable(module_name: str, preferred_names: tuple[str, ...]) -> Callable[..., Any]:
    """Load a pipeline callable without hard-coding a single function name.

    The previous overlays used small, review-only pipeline modules. In local
    branches, the exported function name may differ slightly, so this helper
    accepts a list of conventional names.
    """

    module = importlib.import_module(module_name)
    for name in preferred_names:
        candidate = getattr(module, name, None)
        if callable(candidate):
            return candidate
    raise AttributeError(
        f"{module_name} does not expose any expected callable: "
        + ", ".join(preferred_names)
    )


def run_main_code_review_pipeline(input_path: str | Path, out_dir: str | Path) -> Any:
    """Run the main-code review pipeline.

    This wrapper is deliberately named with ``review`` to avoid implying that it
    performs live CAD execution.
    """

    fn = _load_callable(
        "hscad.pipelines.main_code_pipeline",
        (
            "run_main_code_pipeline",
            "run_pipeline",
            "main_code_pipeline",
            "execute",
        ),
    )
    return fn(input_path=Path(input_path), out_dir=Path(out_dir))


def run_evidence_bridge_review_pipeline(legacy_dir: str | Path, out_dir: str | Path) -> Any:
    """Run the legacy-artifact evidence bridge pipeline."""

    fn = _load_callable(
        "hscad.pipelines.evidence_bridge_pipeline",
        (
            "run_evidence_bridge_pipeline",
            "run_pipeline",
            "evidence_bridge_pipeline",
            "execute",
        ),
    )
    return fn(legacy_dir=Path(legacy_dir), out_dir=Path(out_dir))


def register_review_only_commands(app: Any) -> Any:
    """Register review-only commands on a Typer-compatible app.

    The function returns ``app`` for easier usage in ``src/main.py``:

        from hscad.app.review_cli_registry import register_review_only_commands
        register_review_only_commands(app)
    """

    try:
        import typer  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Typer is required to register review-only CLI commands") from exc

    @app.command(COMMAND_MAIN_CODE)
    def _main_code_pipeline_command(
        input: Path = typer.Option(..., "--input", "-i", help="Input DXF/DWG/PDF/Image path."),
        out: Path = typer.Option(..., "--out", "-o", help="Output directory for review artifacts."),
    ) -> None:
        """Run HS-CAD main-code review pipeline without live CAD execution."""

        result = run_main_code_review_pipeline(input, out)
        typer.echo(str(result))

    @app.command(COMMAND_EVIDENCE_BRIDGE)
    def _evidence_bridge_command(
        legacy_dir: Path = typer.Option(..., "--legacy-dir", help="Directory with existing HS-CAD JSON artifacts."),
        out: Path = typer.Option(..., "--out", "-o", help="Output directory for bridge artifacts."),
    ) -> None:
        """Convert existing HS-CAD artifacts into Evidence/Fusion outputs."""

        result = run_evidence_bridge_review_pipeline(legacy_dir, out)
        typer.echo(str(result))

    return app


__all__ = [
    "COMMAND_MAIN_CODE",
    "COMMAND_EVIDENCE_BRIDGE",
    "register_review_only_commands",
    "run_main_code_review_pipeline",
    "run_evidence_bridge_review_pipeline",
]
