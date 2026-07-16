from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

DEFAULT_EVIDENCE = Path("outputs/orchestrator/latest.json")
MAX_EVIDENCE_BYTES = 2_000_000
MAX_RESULTS = 128
MAX_RESPONSE_BYTES = 65_536
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_LABEL = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SCHEMA_VERSION = re.compile(r"^hscad\.plugin-orchestrator\.v[0-9]+(?:\.[0-9]+)*$")
TOP_LEVEL_STATUSES = {"passed", "failed", "blocked"}
RESULT_STATUSES = {"passed", "failed", "blocked", "timeout", "error"}
PROFILE_NAMES = {"auto", "core", "drawing-index", "semantic", "mobile", "windows-cad"}
RESULT_FIELDS = (
    "name",
    "status",
    "return_code",
    "duration_seconds",
    "stdout_sha256",
    "stderr_sha256",
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="strict")).hexdigest()


def _opaque_token(namespace: str, kind: str, value: str) -> str:
    if not namespace:
        raise ValueError("orchestrator namespace is required")
    if not value:
        raise ValueError(f"{kind} reference is required")
    return _sha256(f"{namespace}:{kind}:{value}")


def _require_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"evidence field '{key}' must be a non-empty string")
    return value.strip()


def _safe_label(value: str, field: str) -> str:
    normalized = value.strip().lower()
    if not SAFE_LABEL.fullmatch(normalized):
        raise ValueError(f"{field} must be a lowercase safe label of at most 64 characters")
    return normalized


def _completed_at(value: str) -> str:
    normalized = value.strip()
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("completed_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("completed_at must include a timezone")
    return parsed.isoformat()


def _require_non_negative_int(mapping: Mapping[str, Any], key: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"summary field '{key}' must be a non-negative integer")
    return value


def _clean_summary(
    value: object,
    *,
    top_level_status: str,
    result_count: int,
) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError("evidence field 'summary' must be an object")
    summary = {
        key: _require_non_negative_int(value, key)
        for key in ("total", "passed", "failed", "blocked")
    }

    selection_failure = {"total": 0, "passed": 0, "failed": 1, "blocked": 0}
    if top_level_status == "failed" and result_count == 0 and summary == selection_failure:
        return {"total": 0, "passed": 0, "failed": 0, "blocked": 0}

    if summary["total"] != summary["passed"] + summary["failed"] + summary["blocked"]:
        raise ValueError("summary counts do not add up to total")
    if summary["total"] != result_count:
        raise ValueError("summary total must equal the number of sanitized results")
    return summary


def _clean_result(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("each result must be an object")

    name = _safe_label(_require_string(value, "name"), "result name")
    status = _require_string(value, "status")
    if status not in RESULT_STATUSES:
        raise ValueError("unsupported result status")

    return_code = value.get("return_code")
    if return_code is not None and (not isinstance(return_code, int) or isinstance(return_code, bool)):
        raise ValueError("result return_code must be an integer or null")

    duration = value.get("duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool):
        raise ValueError("result duration_seconds must be a non-negative finite number")
    duration_number = float(duration)
    if not math.isfinite(duration_number) or duration_number < 0:
        raise ValueError("result duration_seconds must be a non-negative finite number")

    stdout_sha256 = _require_string(value, "stdout_sha256")
    stderr_sha256 = _require_string(value, "stderr_sha256")
    if not HEX_64.fullmatch(stdout_sha256) or not HEX_64.fullmatch(stderr_sha256):
        raise ValueError("result stdout/stderr digests must be lowercase SHA-256 values")

    cleaned = {
        "name": name,
        "status": status,
        "return_code": return_code,
        "duration_seconds": round(duration_number, 3),
        "stdout_sha256": stdout_sha256,
        "stderr_sha256": stderr_sha256,
    }
    assert tuple(cleaned) == RESULT_FIELDS
    return cleaned


def build_record(
    evidence: Mapping[str, Any],
    *,
    repository_ref: str,
    branch_ref: str,
    commit_sha: str,
    runner: str,
    namespace: str,
) -> dict[str, Any]:
    schema_version = _require_string(evidence, "schema_version")
    if not SCHEMA_VERSION.fullmatch(schema_version):
        raise ValueError("unsupported orchestrator schema version format")

    completed_at = _completed_at(_require_string(evidence, "completed_at"))
    status = _require_string(evidence, "status")
    if status not in TOP_LEVEL_STATUSES:
        raise ValueError("unsupported top-level status")
    if not HEX_40.fullmatch(commit_sha):
        raise ValueError("commit SHA must be 40 lowercase hexadecimal characters")

    runner_label = _safe_label(runner, "runner")
    profiles_value = evidence.get("profiles")
    if not isinstance(profiles_value, list) or not profiles_value:
        raise ValueError("evidence field 'profiles' must be a non-empty array")

    profiles: list[str] = []
    for profile in profiles_value:
        if not isinstance(profile, str):
            raise ValueError("every profile must be a string")
        normalized = profile.strip().lower()
        if normalized not in PROFILE_NAMES:
            raise ValueError("unsupported orchestrator profile")
        if normalized in profiles:
            raise ValueError("duplicate orchestrator profile")
        profiles.append(normalized)

    results_value = evidence.get("results")
    if not isinstance(results_value, list):
        raise ValueError("evidence field 'results' must be an array")
    if len(results_value) > MAX_RESULTS:
        raise ValueError(f"evidence may contain at most {MAX_RESULTS} results")

    results = [_clean_result(item) for item in results_value]
    summary = _clean_summary(
        evidence.get("summary"),
        top_level_status=status,
        result_count=len(results),
    )
    sanitized_evidence = {
        "schema_version": schema_version,
        "commit_sha": commit_sha,
        "profiles": profiles,
        "status": status,
        "summary": summary,
        "results": results,
        "runner": runner_label,
        "completed_at": completed_at,
    }
    return {
        "schema_version": schema_version,
        "repository_token": _opaque_token(namespace, "repository", repository_ref),
        "branch_token": _opaque_token(namespace, "branch", branch_ref),
        "commit_sha": commit_sha,
        "profiles": profiles,
        "status": status,
        "summary": summary,
        "results": results,
        "evidence_sha256": _sha256(_canonical_json(sanitized_evidence)),
        "runner": runner_label,
        "completed_at": completed_at,
    }


def publish_record(
    record: Mapping[str, Any],
    *,
    supabase_url: str,
    service_role_key: str,
    timeout: int = 30,
) -> Mapping[str, Any]:
    if not supabase_url.startswith("https://"):
        raise ValueError("HSCAD_SUPABASE_URL must use HTTPS")
    if not service_role_key:
        raise ValueError("HSCAD_SUPABASE_SERVICE_ROLE_KEY is required")

    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/orchestrator_evidence"
    request = urllib.request.Request(
        endpoint,
        data=_canonical_json(dict(record)).encode("utf-8"),
        method="POST",
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=max(1, timeout)) as response:
            raw_payload = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"evidence insert failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("evidence insert endpoint was unreachable") from exc

    if len(raw_payload) > MAX_RESPONSE_BYTES:
        raise RuntimeError("evidence insert response exceeded the allowed size")
    payload = json.loads(raw_payload.decode("utf-8"))
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], Mapping):
        raise RuntimeError("evidence insert returned an unexpected response")
    return payload[0]


def _env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"environment variable {name} is required")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish hash-only orchestrator evidence to a trusted Supabase backend."
    )
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--runner", default=os.getenv("HSCAD_ORCHESTRATOR_RUNNER", "local-container"))
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _safe_failure_message(exc: BaseException) -> str:
    if isinstance(exc, FileNotFoundError):
        return "evidence file was not found"
    if isinstance(exc, PermissionError):
        return "evidence file could not be read"
    if isinstance(exc, OSError):
        return "evidence file operation failed"
    if isinstance(exc, json.JSONDecodeError):
        return "evidence JSON is invalid"
    if isinstance(exc, RuntimeError):
        return str(exc)
    return str(exc)


def main() -> int:
    args = parse_args()
    try:
        if args.evidence.stat().st_size > MAX_EVIDENCE_BYTES:
            raise ValueError(f"evidence file exceeds {MAX_EVIDENCE_BYTES} bytes")
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        if not isinstance(evidence, Mapping):
            raise ValueError("evidence root must be an object")
        record = build_record(
            evidence,
            repository_ref=_env("HSCAD_REPOSITORY_REF"),
            branch_ref=_env("HSCAD_BRANCH_REF"),
            commit_sha=_env("HSCAD_COMMIT_SHA"),
            runner=args.runner,
            namespace=_env("HSCAD_ORCHESTRATOR_NAMESPACE"),
        )
        if args.dry_run:
            print(_canonical_json(record))
            return 0

        inserted = publish_record(
            record,
            supabase_url=_env("HSCAD_SUPABASE_URL"),
            service_role_key=_env("HSCAD_SUPABASE_SERVICE_ROLE_KEY"),
            timeout=args.timeout,
        )
        print(
            _canonical_json(
                {
                    "id": inserted.get("id"),
                    "status": inserted.get("status"),
                    "evidence_sha256": inserted.get("evidence_sha256"),
                }
            )
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"evidence publish failed: {_safe_failure_message(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
