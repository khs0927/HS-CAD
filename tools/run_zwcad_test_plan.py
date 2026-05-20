from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.testing.environment_check import run_environment_check, summarize_environment_check, write_environment_check


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_step(name: str, cmd: list[str], out_dir: Path, results: list[dict[str, Any]]) -> None:
    started = datetime.now().isoformat(timespec="seconds")
    try:
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, capture_output=True, timeout=600)
        ok = proc.returncode == 0
        results.append({"name": name, "ok": ok, "returncode": proc.returncode, "command": cmd, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:], "started": started})
    except Exception as exc:
        results.append({"name": name, "ok": False, "command": cmd, "error": str(exc), "started": started})
    _write_json(out_dir / "test_plan_result.json", {"steps": results})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a safe ZWCAD 2025/2026 test plan. Original DWG is never edited.")
    parser.add_argument("--version", choices=["2025", "2026"], help="Preferred ZWCAD version")
    parser.add_argument("--dwg", required=True, help="Sample DWG path. This file is never edited directly.")
    parser.add_argument("--xicad-root", help="Optional XiCAD root path")
    parser.add_argument("--out-dir", default="outputs/zwcad_test_plan", help="Output directory")
    parser.add_argument("--start-zwcad", action="store_true", help="Allow COM to start ZWCAD")
    parser.add_argument("--execute-smoke", action="store_true", help="Run a minimal edit smoke test on a copied DWG only")
    parser.add_argument("--move-layer", default="MARK", help="Layer to move during execute smoke test")
    parser.add_argument("--dx", type=float, default=0.0)
    parser.add_argument("--dy", type=float, default=0.0)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, Any]] = []
    dwg = Path(args.dwg)

    env_payload = run_environment_check(
        dwg=args.dwg,
        xicad_root=args.xicad_root,
        version=args.version,
        start_zwcad=args.start_zwcad,
        project_root=PROJECT_ROOT,
    )
    write_environment_check(env_payload, out_dir / "env_check")
    steps.append({"name": "env-check", "ok": True, "connected": env_payload.get("zwcad_com_connected"), "active_progid": env_payload.get("zwcad_active_progid")})

    py = sys.executable
    if dwg.exists():
        _run_step("scan", [py, "-m", "src.main", "scan", "--dwg", str(dwg), "--out", str(out_dir / "scan" / "objects.json")], out_dir, steps)
        _run_step("classify-objects", [py, "-m", "src.main", "classify-objects", "--input-json", str(out_dir / "scan" / "objects.json"), "--out", str(out_dir / "semantics" / "object_semantics.json")], out_dir, steps)
        _run_step("analyze-architecture", [py, "-m", "src.main", "analyze-architecture", "--dwg", str(dwg), "--out-dir", str(out_dir / "architecture_report")], out_dir, steps)
        _run_step("collect-debug", [py, "-m", "src.main", "collect-debug", "--dwg", str(dwg), "--out-dir", str(out_dir / "debug_bundle")], out_dir, steps)
    else:
        steps.append({"name": "dwg-exists", "ok": False, "error": f"DWG not found: {dwg}"})

    if args.xicad_root:
        _run_step("detect-xicad", [py, "-m", "src.main", "detect-xicad", "--xicad-root", args.xicad_root], out_dir, steps)
        _run_step("xicad-catalog", [py, "-m", "src.main", "xicad-catalog", "--xicad-root", args.xicad_root], out_dir, steps)

    if args.execute_smoke and dwg.exists():
        smoke_dir = out_dir / "smoke_modify"
        smoke_dir.mkdir(parents=True, exist_ok=True)
        copy_path = smoke_dir / f"{dwg.stem}_copy{dwg.suffix}"
        save_path = smoke_dir / f"{dwg.stem}_smoke_modified{dwg.suffix}"
        shutil.copy2(dwg, copy_path)
        cmd_path = smoke_dir / "move_layer_smoke.json"
        _write_json(cmd_path, {"command": "move_layer", "params": {"layer": args.move_layer, "dx": args.dx, "dy": args.dy, "dz": 0}})
        _run_step("execute-smoke-copy-only", [py, "-m", "src.main", "run-command", "--dwg", str(copy_path), "--command", str(cmd_path), "--execute", "--no-dry-run", "--save-as", str(save_path)], out_dir, steps)

    ok = all(step.get("ok") for step in steps if step.get("name") != "dwg-exists")
    result = {"ok": ok, "version": args.version, "original_dwg": str(dwg), "out_dir": str(out_dir), "steps": steps}
    _write_json(out_dir / "test_plan_result.json", result)
    md = ["# ZWCAD Safe Test Plan Result", "", f"- Version: {args.version or 'auto'}", f"- Original DWG: {dwg}", "- Original DWG modified: no", ""]
    for step in steps:
        md.append(f"- {step.get('name')}: {'OK' if step.get('ok') else 'FAILED'}")
    (out_dir / "test_plan_result.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"Wrote outputs to: {out_dir}")


if __name__ == "__main__":
    main()
