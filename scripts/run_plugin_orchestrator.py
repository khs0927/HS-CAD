from __future__ import annotations

import argparse
import hashlib
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
    working_directory: str = "."
    required_paths: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    description: str = ""


@dataclass
class CheckResult:
    name: str
    status: str
    command: list[str]
    working_directory: str
    return_code: int | None
    duration_seconds: float
    stdout_sha256: str
    stderr_sha256: str
    stdout: str = ""
    stderr: str = ""
    reason: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _tail(value: str) -> str:
    return value[-MAX_CAPTURE_CHARS:]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _sanitize_text(value: str, fixture_root: str | None) -> str:
    replacements = [
        (str(ROOT), "<repo-root>"),
        (str(Path.home()), "<home>"),
        (sys.executable, "<python>"),
    ]
    if fixture_root:
        replacements.append((fixture_root, "<fixture-root>"))

    sanitized = value
    for source, replacement in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        if source:
            sanitized = sanitized.replace(source, replacement)
    return sanitized


def _safe_command(command: Sequence[str], fixture_root: str | None) -> list[str]:
    return [_sanitize_text(part, fixture_root) for part in command]


def _resolve_working_directory(check: Check) -> Path:
    root = ROOT.resolve()
    candidate = (ROOT / check.working_directory).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"working directory escapes repository root: {check.working_directory}"
        ) from exc
    return candidate


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
            "tests/test_corpus_foundation.py",
            "tests/test_drawing_index_v2.py",
            "tests/test_drawing_index_architecture.py",
            "tests/test_drawing_index_fallback_resilience.py",
            "tests/test_compare_drawing_index_fixture_runs.py",
            "tests/test_free_only_runtime.py",
            "tests/test_supabase_summary_privacy.py",
            "tests/test_drawing_index_privacy.py",
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


def _mobile_checks() -> list[Check]:
    app_dir = "apps/mobile-cad-chatgpt"
    package_json = f"{app_dir}/package.json"
    lock_file = f"{app_dir}/package-lock.json"
    if not (ROOT / package_json).exists():
        return []
    required = (package_json, lock_file)
    return [
        Check(
            name="mobile-node-version",
            command=(
                "node",
                "-e",
                "const [a,b]=process.versions.node.split('.').map(Number); process.exit(a>22 || (a===22 && b>=18) ? 0 : 1)",
            ),
            working_directory=app_dir,
            required_paths=required,
            description="Require Node.js 22.18 or newer.",
        ),
        Check(
            name="mobile-npm-clean-install",
            command=("npm", "ci", "--no-audit", "--no-fund"),
            working_directory=app_dir,
            required_paths=required,
            description="Install the exact package-lock dependency graph.",
        ),
        Check(
            name="mobile-validation",
            command=("npm", "run", "validate:ci"),
            working_directory=app_dir,
            required_paths=required,
            description="Run typecheck, tests, bootstrap tests, UI build, bundle check and Worker dry-run.",
        ),
        Check(
            name="mobile-security",
            command=("npm", "run", "security:local"),
            working_directory=app_dir,
            required_paths=required,
            description="Run local license and secret scans.",
        ),
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


def _checks_for_profile(profile: str, fixture_root: str | None) -> list[Check]:
    if profile == "core":
        return _portable_checks()
    if profile == "drawing-index":
        return _drawing_index_checks()
    if profile == "semantic":
        return _semantic_checks()
    if profile == "mobile":
        return _mobile_checks()
    if profile == "windows-cad":
        return _windows_fixture_check(fixture_root)
    raise ValueError(f"unknown profile: {profile}")


def build_checks(profiles: Iterable[str], fixture_root: str | None) -> tuple[list[str], list[Check]]:
    requested = list(dict.fromkeys(profiles))
    if "auto" in requested and len(requested) > 1:
        raise ValueError("profile 'auto' cannot be combined with explicit profiles")

    automatic = not requested or requested == ["auto"]
    if automatic:
        requested = ["core"]
        if (ROOT / "src/drawing_index").exists():
            requested.append("drawing-index")
        if (ROOT / "src/semantic_index").exists():
            requested.append("semantic")
        if (ROOT / "apps/mobile-cad-chatgpt/package.json").exists():
            requested.append("mobile")
        if fixture_root:
            requested.append("windows-cad")

    checks: list[Check] = []
    for profile in requested:
        profile_checks = _checks_for_profile(profile, fixture_root)
        if not profile_checks:
            raise ValueError(f"profile '{profile}' has no runnable checks in this branch/environment")
        checks.extend(profile_checks)
    if not checks:
        raise ValueError("no validation checks were selected")
    return requested, checks


def _result(
    *,
    check: Check,
    status: str,
    return_code: int | None,
    duration_seconds: float,
    stdout: str,
    stderr: str,
    fixture_root: str | None,
    include_logs: bool,
    reason: str = "",
) -> CheckResult:
    safe_stdout = _sanitize_text(stdout, fixture_root)
    safe_stderr = _sanitize_text(stderr, fixture_root)
    return CheckResult(
        name=check.name,
        status=status,
        command=_safe_command(check.command, fixture_root),
        working_directory=_sanitize_text(check.working_directory, fixture_root),
        return_code=return_code,
        duration_seconds=round(duration_seconds, 3),
        stdout_sha256=_digest(safe_stdout),
        stderr_sha256=_digest(safe_stderr),
        stdout=_tail(safe_stdout) if include_logs else "",
        stderr=_tail(safe_stderr) if include_logs else "",
        reason=_sanitize_text(reason, fixture_root),
    )


def run_check(
    check: Check,
    *,
    timeout: int,
    fixture_root: str | None,
    include_logs: bool,
) -> CheckResult:
    current_platform = platform.system()
    try:
        working_directory = _resolve_working_directory(check)
    except ValueError as exc:
        return _result(
            check=check,
            status="error",
            return_code=None,
            duration_seconds=0.0,
            stdout="",
            stderr="",
            fixture_root=fixture_root,
            include_logs=include_logs,
            reason=str(exc),
        )

    missing = [path for path in check.required_paths if not (ROOT / path).exists()]
    if missing:
        return _result(
            check=check,
            status="failed",
            return_code=None,
            duration_seconds=0.0,
            stdout="",
            stderr="",
            fixture_root=fixture_root,
            include_logs=include_logs,
            reason=f"missing required paths: {', '.join(missing)}",
        )
    if check.platforms and current_platform not in check.platforms:
        return _result(
            check=check,
            status="blocked",
            return_code=None,
            duration_seconds=0.0,
            stdout="",
            stderr="",
            fixture_root=fixture_root,
            include_logs=include_logs,
            reason=f"requires platform: {', '.join(check.platforms)}",
        )

    started = time.monotonic()
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    try:
        completed = subprocess.run(
            list(check.command),
            cwd=working_directory,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return _result(
            check=check,
            status="timeout",
            return_code=None,
            duration_seconds=time.monotonic() - started,
            stdout=_to_text(exc.stdout),
            stderr=_to_text(exc.stderr),
            fixture_root=fixture_root,
            include_logs=include_logs,
            reason=f"exceeded {timeout} seconds",
        )
    except OSError as exc:
        return _result(
            check=check,
            status="error",
            return_code=None,
            duration_seconds=time.monotonic() - started,
            stdout="",
            stderr="",
            fixture_root=fixture_root,
            include_logs=include_logs,
            reason=f"{type(exc).__name__}: {exc}",
        )

    return _result(
        check=check,
        status="passed" if completed.returncode == 0 else "failed",
        return_code=completed.returncode,
        duration_seconds=time.monotonic() - started,
        stdout=completed.stdout,
        stderr=completed.stderr,
        fixture_root=fixture_root,
        include_logs=include_logs,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the HS-CAD validation contract without GitHub Actions."
    )
    parser.add_argument(
        "--profile",
        action="append",
        choices=("auto", "core", "drawing-index", "semantic", "mobile", "windows-cad"),
        default=[],
        help="Repeat to combine explicit profiles. The default auto-detects available modules.",
    )
    parser.add_argument("--fixture-root", help="Private fixture directory for the Windows/ZWCAD gate.")
    parser.add_argument("--timeout", type=int, default=1200, help="Timeout per check in seconds.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="JSON evidence output path.")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument(
        "--include-logs",
        action="store_true",
        help="Include sanitized stdout/stderr tails. Default evidence contains hashes only.",
    )
    return parser.parse_args()


def _write_payload(output: Path, payload: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    started_at = utc_now()
    try:
        resolved_profiles, checks = build_checks(args.profile or ["auto"], args.fixture_root)
    except ValueError as exc:
        payload = {
            "schema_version": "hscad.plugin-orchestrator.v1.1",
            "started_at": started_at,
            "completed_at": utc_now(),
            "status": "failed",
            "profiles": args.profile or ["auto"],
            "log_capture": "included" if args.include_logs else "hash-only",
            "orchestrator_error": str(exc),
            "summary": {"total": 0, "passed": 0, "failed": 1, "blocked": 0},
            "results": [],
        }
        _write_payload(args.output, payload)
        print(f"[FAILED] {exc}")
        print(f"Evidence: {args.output}")
        return 2

    results: list[CheckResult] = []
    for check in checks:
        result = run_check(
            check,
            timeout=max(1, args.timeout),
            fixture_root=args.fixture_root,
            include_logs=args.include_logs,
        )
        results.append(result)
        print(f"[{result.status.upper()}] {result.name} ({result.duration_seconds:.3f}s)")
        if result.status != "passed" and not args.continue_on_error:
            break

    failed = [item for item in results if item.status != "passed"]
    payload = {
        "schema_version": "hscad.plugin-orchestrator.v1.1",
        "started_at": started_at,
        "completed_at": utc_now(),
        "status": "failed" if failed else "passed",
        "profiles": resolved_profiles,
        "log_capture": "included" if args.include_logs else "hash-only",
        "environment": {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "executable": "<python>",
            "working_directory": "<repo-root>",
        },
        "summary": {
            "total": len(results),
            "passed": sum(item.status == "passed" for item in results),
            "failed": sum(item.status in {"failed", "timeout", "error"} for item in results),
            "blocked": sum(item.status == "blocked" for item in results),
        },
        "results": [asdict(item) for item in results],
    }
    _write_payload(args.output, payload)
    print(f"Evidence: {args.output}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
