from __future__ import annotations
import sys
from pathlib import Path
from typer.testing import CliRunner

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

def test_cli_utf8_safe():
    """Verify that CLI output and help command execute successfully without throwing encoding errors."""
    from neuro_seq_cad.app.cli import app
    
    runner = CliRunner()
    
    # Run the main cli help command
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "analyze" in result.stdout
    assert "export-dxf" in result.stdout
    
    # Run analyze help command
    result_analyze = runner.invoke(app, ["analyze", "--help"])
    assert result_analyze.exit_code == 0
    assert "dry-run" in result_analyze.stdout
