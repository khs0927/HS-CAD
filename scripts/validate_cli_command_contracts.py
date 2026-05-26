# scripts/validate_cli_command_contracts.py
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

# Repository Root Setup
repo_root = pathlib.Path(__file__).resolve().parent.parent

# Prohibited patterns for live CAD execution / unsafe operations in CLI descriptions
PROHIBITED_PATTERN = re.compile(
    r"\bSendCommand\b|\bSaveAs\b|\bDXFOUT\b|\bXiCAD\b|\bZWCAD\b|\bAutoCAD\b|\bCOM\b|\boriginal_dwg\b|\bmutation\b|\bmutate\b|live runner|\bZWCADCOMAdapter\b|\bwin32com\b|\bpyautocad\b",
    re.I
)

# Known safe phrases that are allowed (preflight messages indicating no-op / safety gates)
SAFE_ALLOWLIST = [
    "does not execute cad",
    "does not merge main",
    "does not implement runner",
    "no-com",
    "safety planning",
    "preflight guard"
]

def clean_and_scan_help_text(text: str) -> list[str]:
    violations = []
    for line in text.splitlines():
        # Lowercase safe phrase check
        line_lower = line.lower()
        if any(safe_phrase in line_lower for safe_phrase in SAFE_ALLOWLIST):
            continue
        
        # Check prohibited pattern
        matches = PROHIBITED_PATTERN.findall(line)
        if matches:
            violations.append(f"Line: {line.strip()} (matches: {', '.join(set(matches))})")
    return violations

def discover_commands() -> list[str]:
    # Static fallback of known core command groups
    commands = {
        "connect", "scan", "layers", "blocks", "texts", "analyze-architecture",
        "hscad-spatial-containment", "hscad-text-roles", "hscad-workers", "hscad-worker-run",
        "corpus-run", "hscad-qa"
    }

    try:
        # Run main --help to dynamically discover commands
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        if result.returncode == 0:
            # Parse unicode box lines like: │ command-name   │
            pattern = re.compile(r"│\s*([a-zA-Z0-9_-]+)\s*│")
            for line in result.stdout.splitlines():
                match = pattern.search(line)
                if match:
                    cmd = match.group(1).strip()
                    # Skip common options or non-commands if parsed
                    if cmd not in {"help", "version", "options"}:
                        commands.add(cmd)
    except Exception:
        pass

    return sorted(list(commands))

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CLI command contracts")
    parser.add_argument("--strict", action="store_true", help="Fail and return exit code 1 if any command is invalid")
    args = parser.parse_args()

    commands = discover_commands()
    print(f"Discovered {len(commands)} CLI commands for safety validation...\n")

    results = {}
    has_failures = False

    # First validate main help itself
    try:
        main_help_res = subprocess.run(
            [sys.executable, "-m", "src.main", "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        main_violations = clean_and_scan_help_text(main_help_res.stdout) if main_help_res.returncode == 0 else ["Main command failed to execute"]
        
        results["_main_"] = {
            "status": "ok" if (main_help_res.returncode == 0 and not main_violations) else "failed",
            "returncode": main_help_res.returncode,
            "violations": main_violations,
            "message": "Main entrypoint help parsed successfully" if main_help_res.returncode == 0 else "Failed to run main --help"
        }
        if results["_main_"]["status"] == "failed":
            has_failures = True
    except Exception as exc:
        results["_main_"] = {
            "status": "failed",
            "returncode": -1,
            "violations": [str(exc)],
            "message": f"Exception occurred while calling main --help: {exc}"
        }
        has_failures = True

    # Validate each sub-command
    for cmd in commands:
        try:
            res = subprocess.run(
                [sys.executable, "-m", "src.main", cmd, "--help"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10
            )
            
            if res.returncode != 0:
                results[cmd] = {
                    "status": "execution_failed",
                    "returncode": res.returncode,
                    "violations": [f"Command exited with non-zero code {res.returncode}"],
                    "message": f"Command '{cmd} --help' failed to execute."
                }
                has_failures = True
                continue

            violations = clean_and_scan_help_text(res.stdout)
            if violations:
                results[cmd] = {
                    "status": "prohibited_keyword_found",
                    "returncode": res.returncode,
                    "violations": violations,
                    "message": f"Command '{cmd}' contains prohibited live CAD / mutation keywords in its help text."
                }
                has_failures = True
            else:
                results[cmd] = {
                    "status": "ok",
                    "returncode": res.returncode,
                    "violations": [],
                    "message": f"Successfully verified contract for '{cmd}'."
                }

        except subprocess.TimeoutExpired:
            results[cmd] = {
                "status": "timeout",
                "returncode": -1,
                "violations": ["Command help took longer than 10 seconds to execute"],
                "message": f"Command '{cmd} --help' timed out."
            }
            has_failures = True
        except Exception as exc:
            results[cmd] = {
                "status": "error",
                "returncode": -1,
                "violations": [str(exc)],
                "message": f"Error validating command '{cmd}': {exc}"
            }
            has_failures = True

    # Build report
    report = {
        "summary": {
            "total_commands_scanned": len(commands) + 1,  # commands + main
            "ok_count": sum(1 for r in results.values() if r["status"] == "ok"),
            "failed_count": sum(1 for r in results.values() if r["status"] != "ok"),
            "strict_mode": args.strict,
            "has_failures": has_failures
        },
        "results": results
    }

    # Print summary table
    print("-" * 100)
    print(f"{'Command':<45} | {'Status':<30} | {'Notes'}")
    print("-" * 100)
    for cmd, r in results.items():
        print(f"{cmd:<45} | {r['status']:<30} | {r['message'][:50]}")
    print("-" * 100)

    # Save to outputs
    output_dir = repo_root / "outputs"
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / "cli_command_contracts_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nCLI contracts report saved to {report_path}")

    if args.strict and has_failures:
        print("\n[STRICT MODE] CLI contracts validation failed due to unsafe keywords or execution errors.", file=sys.stderr)
        return 1

    print("\nCLI contracts validation finished successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
