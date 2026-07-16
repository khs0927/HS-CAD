from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "outputs" / "orchestrator" / "latest.json"
MAX_CAPTURE_CHARS = 40_000


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]
    required_paths: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    description: str = ""


@dataclass
class CheckResult:
    name: str
    status: str
    command: list[str]
    return_code: int | None
    duration_seconds: float
    stdout: str
    stderr: str
    reason: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tail(value: str) -> str:
    return value[-MAX_CAPTURE_CHARS:]


def _safe_command(command: Sequence[str], fixture_root: str | None) -> list[str]:
    safe = list(command)
    if fixture_root:
        safe = [part.replace(fixture_root, "<fixture-root>") for part in safe]
    return safe


def _portable_checks() -> list[Check]:
    py = sys.executable
    return [
        Check(
            name="compile",
            command=(py, "-m", "compileall", "-q", "src", "scripts"),
            required_paths=("src", "scripts"),
            description="Compile portable Python sources.",
        ),
        Check(
            name="portable-tests",
            command=(
                py,
                "-m",
                "pytest",
                "-q",
                "--disable-warnings",
                "--maxfail=1",
                "-m",
                "not windows and not zwcad and not integration",
            ),
            required_paths=("tests",),
            description="Run tests that do not require Windows, ZWCAD, or an external system.",
        ),
        Check(
            name="ruff",
            command=(py, "-m", "ruff", "check", "src", "tests", "scripts"),
            required_paths=("src", "tests", "scripts"),
            description="Run repository lint rules.",
        ),
        Check(
            name="wheel-build",
            command=(
                py,
                "-m",
                "build",
                "--wheel",
                "--outdir",
                "outputs/orchestrator/dist",
            ),
            required_paths=("pyproject.toml",),
            description="Build a wheel without GitHub Actions.",
        ),
    ]


def _drawing_index_checks() -> list[Check]:
    py = sys.executable
    tests = tuple(
        path
        for path in (
            "tests/test_drawing_index_v2.py",
            "tests/test_drawing_index_architecture.py",
            "tests/test_drawing_index_fallback_resilience.py",
            "tests/test_free_only_runtime.py",
            "tests/test_orchestrator_privacy.py",
        )
        if (ROOT / path).exists()
    )
    checks: list[Check] = []
    if (ROOT / "scripts/validate_free_only.py").exists():
        checks.append(
            Check(
                name="drawing-index-free-only-policy",
                command=(py, "scripts/validate_free_only.py"),
                required_paths=("scripts/validate_free_only.py",),
            )
        )
    if (ROOT / "scripts/validate_drawing_index_v2.py").exists():
        checks.append(
            Check(
                name="drawing-index-contract",
                command=(py, "scripts/validate_drawing_index_v2.py"),
                required_paths=("scripts/validate_drawing_index_v2.py",),
            )
        )
    if tests:
        checks.append(
            Check(
                name="drawing-index-tests",
                command=(py, "-m", "pytest", "-q", "--disable-warnings", "--maxfail=1", *tests),
                required_paths=tests,
            )
        )
    return checks


def _semantic_checks() -> list[Check]:
    py = sys.executable
    tests = tuple(
        str(path.relative_to(ROOT))
        for path in sorted((ROOT / "tests").glob("test_semantic_index*.py"))
    )
    if not tests:
        return []
    return [
        Check(
            name="semantic-index-tests",
            command=(py, "-m", "pytest", "-q", "--disable-warnings", "--maxfail=1", *tests),
            required_paths=tests,
        )
    ]


def _windows_fixture_check(fixture_root: str | None) -> list[Check]:
    script = "scripts/run_windows_drawing_index_fixture_matrix.ps1"
    if not fixture_root or not (ROOT / script).exists():
        return []
    return [
        Check(
            name="windows-zwcad-fixture-matrix",
            command=(
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script,
                "-Root",
                fixture_root,
                "-Workspace",
                "outputs/orchestrator/windows-fixture-matrix",
            ),
            required_paths=(script,),
            platforms=("Windows",),
            description="Run the real Windows 11 + ZWCAD fixture acceptance gate.",
        )
    ]


def build_checks(profiles: Iterable[str], fixture_root: str | None) -> list[Check]:
    requested = list(dict.fromkeys(profiles))
    if not requested or requested == ["auto"]:
        requested = ["core"]
        if (ROOT / "src/drawing_index").exists():
            requested.append("drawing-index")
        if (ROOT / "src/semantic_index").exists():
            requested.append("semantic")
        if fixture_root:
            requested.append("windows-cad")

    checks: list[Check] = []
    for profile in requested:
        if profile == "core":
            checks.extend(_portable_checks())
        elif profile == "drawing-index":
            checks.extend(_drawing_index_checks())
        elif profile == "semantic":
            checks.extend(_semantic_checks())
        elif profile == "windows-cad":
            checks.extend(_windows_fixture_check(fixture_root))
        else:
            raise ValueError(f"unknown profile: {profile}")
    return checks


def run_check(check: Check, *, timeout: int, fixture_root: str | None) -> CheckResult:
    current_platform = platform.system()
    missing = [path for path in check.required_paths if not (ROOT / path).exists()]
    if missing:
        return CheckResult(
            name=check.name,
            status="skipped",
            command=_safe_command(check.command, fixture_root),
            return_code=None,
            duration_seconds=0.0,
            stdout="",
            stderr="",
            reason=f"missing required paths: {', '.join(missing)}",
        )
    if check.platforms and current_platform not in check.platforms:
        return CheckResult(
            name=check.name,
            status="skipped",
            command=_safe_command(check.command, fixture_root),
            return_code=None,
            duration_seconds=0.0,
            stdout="",
            stderr="",
            reason=f"requires platform: {', '.join(check.platforms)}",
        )

    started = time.monotonic()
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    try:
        completed = subprocess.run(
            list(check.command),
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CheckResult(
            name=check.name,
            status="timeout",
            command=_safe_command(check.command, fixture_root),
            return_code=None,
            duration_seconds=round(time.monotonic() - started, 3),
            stdout=_tail(exc.stdout or ""),
            stderr=_tail(exc.stderr or ""),
            reason=f"exceeded {timeout} seconds",
        )
    except OSError as exc:
        return CheckResult(
            name=check.name,
            status="error",
            command=_safe_command(check.command, fixture_root),
            return_code=None,
            duration_seconds=round(time.monotonic() - started, 3),
            stdout="",
            stderr="",
            reason=f"{type(exc).__name__}: {exc}",
        )

    return CheckResult(
        name=check.name,
        status="passed" if completed.returncode == 0 else "failed",
        command=_safe_command(check.command, fixture_root),
        return_code=completed.returncode,
        duration_seconds=round(time.monotonic() - started, 3),
        stdout=_tail(completed.stdout),
        stderr=_tail(completed.stderr),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the HS-CAD validation contract without GitHub Actions."
    )
    parser.add_argument(
        "--profile",
        action="append",
        choices=("auto", "core", "drawing-index", "semantic", "windows-cad"),
        default=[],
        help="Repeat to combine profiles. The default auto-detects available modules.",
    )
    parser.add_argument("--fixture-root", help="Private fixture directory for the Windows/ZWCAD gate.")
    parser.add_argument("--timeout", type=int, default=1200, help="Timeout per check in seconds.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="JSON evidence output path.")
    parser.add_argument("--continue-on-error", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = utc_now()
    checks = build_checks(args.profile or ["auto"], args.fixture_root)
    results: list[CheckResult] = []

    for check in checks:
        result = run_check(check, timeout=max(1, args.timeout), fixture_root=args.fixture_root)
        results.append(result)
        print(f"[{result.status.upper()}] {result.name} ({result.duration_seconds:.3f}s)")
        if result.status not in {"passed", "skipped"} and not args.continue_on_error:
            break

    failed = [item for item in results if item.status not in {"passed", "skipped"}]
    payload = {
        "schema_version": "hscad.plugin-orchestrator.v1",
        "started_at": started_at,
        "completed_at": utc_now(),
        "status": "failed" if failed else "passed",
        "profiles": args.profile or ["auto"],
        "environment": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "working_directory": str(ROOT),
        },
        "summary": {
            "total": len(results),
            "passed": sum(item.status == "passed" for item in results),
            "failed": len(failed),
            "skipped": sum(item.status == "skipped" for item in results),
        },
        "results": [asdict(item) for item in results],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Evidence: {args.output}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
