# tests/test_cli_help_contracts.py
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import pytest

# Find repository root
ROOT = pathlib.Path(__file__).resolve().parent.parent

# Prohibited patterns
PROHIBITED_PATTERN = re.compile(
    r"\bSendCommand\b|\bSaveAs\b|\bDXFOUT\b|\bXiCAD\b|\bZWCAD\b|\bAutoCAD\b|\bCOM\b|\boriginal_dwg\b|\bmutation\b|\bmutate\b|live runner|\bZWCADCOMAdapter\b|\bwin32com\b|\bpyautocad\b",
    re.I
)

# Known safe phrases
SAFE_ALLOWLIST = [
    "does not execute cad",
    "does not merge main",
    "does not implement runner",
    "no-com",
    "safety planning",
    "preflight guard"
]

# Static list of core command groups in src.main for parameterization
COMMANDS = [
    "connect", "scan", "layers", "blocks", "texts", "analyze-architecture",
    "hscad-spatial-containment", "hscad-text-roles", "hscad-workers", "hscad-worker-run",
    "corpus-run", "hscad-qa"
]

def is_safe_phrase(line: str) -> bool:
    line_lower = line.lower()
    return any(safe in line_lower for safe in SAFE_ALLOWLIST)

@pytest.mark.parametrize("command", COMMANDS)
def test_cli_command_help_contract(command):
    try:
        res = subprocess.run(
            [sys.executable, "-m", "src.main", command, "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"Command '{command} --help' timed out (took > 10s)")
    
    assert res.returncode == 0, f"Command '{command} --help' failed with exit code {res.returncode}"
    
    # Check for prohibited keywords
    violations = []
    for line in res.stdout.splitlines():
        if is_safe_phrase(line):
            continue
        matches = PROHIBITED_PATTERN.findall(line)
        if matches:
            violations.append(f"Line: {line.strip()} (matches: {', '.join(set(matches))})")
            
    assert not violations, f"Command '{command}' help text contains prohibited live CAD keywords: {violations}"

def test_run_worker_manifest_validation_script():
    script_path = ROOT / "scripts" / "validate_worker_manifest_candidates.py"
    assert script_path.exists(), f"Validator script not found at {script_path}"
    
    res = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    assert res.returncode == 0, f"Worker manifest validator script failed with exit code {res.returncode}: {res.stderr}\nStdout: {res.stdout}"
