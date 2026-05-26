# scripts/validate_worker_manifest_candidates.py
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
from pathlib import Path

# Add repository root to sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Prohibited keywords for live CAD execution in workers
PROHIBITED_KEYWORDS = re.compile(
    r"\bSendCommand\b|\bSaveAs\b|\bDXFOUT\b|\bXiCAD\b|\bZWCAD\b|\bAutoCAD\b|\bCOM\b|\boriginal_dwg\b|\bmutation\b|\bmutate\b|live runner|\bZWCADCOMAdapter\b|\bwin32com\b|\bpyautocad\b",
    re.I
)

def scan_file_for_prohibited_keywords(file_path: str) -> list[str]:
    found = []
    if not os.path.exists(file_path):
        return found
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, 1):
                # Simple ignore comments that explicitly mention security boundaries or rules
                if "#" in line:
                    line_code = line.split("#")[0]
                else:
                    line_code = line
                matches = PROHIBITED_KEYWORDS.findall(line_code)
                if matches:
                    found.append(f"Line {idx}: {', '.join(set(matches))}")
    except Exception:
        pass
    return found

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate worker manifest candidates")
    parser.add_argument("--manifest", type=str, default="config/worker_manifest.json", help="Path to manifest JSON")
    parser.add_argument("--strict", action="store_true", help="Fail and return exit code 1 if any entry is invalid")
    args = parser.parse_args()

    manifest_path = repo_root / args.manifest
    if not manifest_path.exists():
        print(f"Error: Manifest file not found at {manifest_path}", file=sys.stderr)
        return 1

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
    except Exception as exc:
        print(f"Error loading manifest JSON: {exc}", file=sys.stderr)
        return 1

    workers = manifest_data.get("workers", {})
    results = {}
    has_failures = False

    print(f"Scanning {len(workers)} worker manifest entries...\n")

    for w_id, w_info in workers.items():
        module_path = w_info.get("module") or w_info.get("path")
        callable_name = w_info.get("callable") or "run_worker"
        
        if not module_path:
            results[w_id] = {
                "status": "missing_module",
                "message": "Neither 'module' nor 'path' is defined in the manifest entry.",
                "details": []
            }
            has_failures = True
            continue

        try:
            mod = importlib.import_module(module_path)
            
            # Check callable
            if not hasattr(mod, callable_name):
                results[w_id] = {
                    "status": "missing_callable",
                    "message": f"Module '{module_path}' imported successfully, but callable '{callable_name}' was not found.",
                    "details": []
                }
                has_failures = True
                continue
            
            # Keyword scan in source file
            mod_file = getattr(mod, "__file__", "")
            keyword_violations = []
            if mod_file:
                keyword_violations = scan_file_for_prohibited_keywords(mod_file)
            
            if keyword_violations:
                results[w_id] = {
                    "status": "review_required_live_cad_keyword",
                    "message": f"Module '{module_path}' contains prohibited CAD/mutation keywords.",
                    "details": keyword_violations
                }
                has_failures = True
            else:
                results[w_id] = {
                    "status": "ok",
                    "message": f"Successfully verified module '{module_path}' with callable '{callable_name}'.",
                    "details": []
                }

        except Exception as exc:
            results[w_id] = {
                "status": "import_failed",
                "message": f"Failed to import module '{module_path}': {type(exc).__name__}: {exc}",
                "details": []
            }
            has_failures = True

    # Generate summary JSON report
    report = {
        "summary": {
            "total_workers": len(workers),
            "ok_count": sum(1 for r in results.values() if r["status"] == "ok"),
            "failed_count": sum(1 for r in results.values() if r["status"] != "ok"),
            "strict_mode": args.strict,
            "has_failures": has_failures
        },
        "results": results
    }

    # Print summary table
    print("-" * 100)
    print(f"{'Worker ID':<45} | {'Status':<35} | {'Notes'}")
    print("-" * 100)
    for w_id, r in results.items():
        print(f"{w_id:<45} | {r['status']:<35} | {r['message'][:50]}")
    print("-" * 100)

    # Save validation report
    output_dir = repo_root / "outputs"
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / "worker_manifest_validation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nValidation report saved to {report_path}")

    if args.strict and has_failures:
        print("\n[STRICT MODE] Validation failed due to one or more non-ok entries.", file=sys.stderr)
        return 1
    
    print("\nWorker validation finished successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
