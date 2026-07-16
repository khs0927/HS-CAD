from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping

DEFAULT_EVIDENCE = Path("outputs/orchestrator/latest.json")
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
TOP_LEVEL_STATUSES = {"passed", "failed", "blocked"}
RESULT_STATUSES = {"passed", "failed", "blocked", "timeout", "error"}
RESULT_FIELDS = (
    "name",
    "status",
    "return_code",
    "duration_seconds",
    "stdout_sha256",
    "stderr_sha256",
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


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

    orchestrator_selection_failure = {
        "total": 0,
        "passed": 0,
        "failed": 1,
        "blocked": 0,
    }
    if (
        top_level_status == "failed"
        and result_count == 0
        and summary == orchestrator_selection_failure
    ):
        return {"total": 0, "passed": 0, "failed": 0, "blocked": 0}

    if summary["total"] != summary["passed"] + summary["failed"] + summary["blocked"]:
        raise ValueError("summary counts do not add up to total")
    if summary["total"] != result_count:
        raise ValueError("summary total must equal the number of sanitized results")
    return summary


def _clean_result(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("each result must be an object")

    name = _require_string(value, "name")
    status = _require_string(value, "status")
    if status not in RESULT_STATUSES:
        raise ValueError(f"unsupported result status: {status}")

    return_code = value.get("return_code")
    if return_code is not None and (not isinstance(return_code, int) or isinstance(return_code, bool)):
        raise ValueError("result return_code must be an integer or null")

    duration = value.get("duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0:
        raise ValueError("result duration_seconds must be a non-negative number")

    stdout_sha256 = _require_string(value, "stdout_sha256")
    stderr_sha256 = _require_string(value, "stderr_sha256")
    if not HEX_64.fullmatch(stdout_sha256) or not HEX_64.fullmatch(stderr_sha256):
        raise ValueError("result stdout/stderr digests must be lowercase SHA-256 values")

    cleaned = {
        "name": name,
        "status": status,
        "return_code": return_code,
        "duration_seconds": round(float(duration), 3),
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
    completed_at = _require_string(evidence, "completed_at")
    status = _require_string(evidence, "status")
    if status not in TOP_LEVEL_STATUSES:
        raise ValueError(f"unsupported top-level status: {status}")

    if not HEX_40.fullmatch(commit_sha):
        raise ValueError("commit SHA must be 40 lowercase hexadecimal characters")

    profiles_value = evidence.get("profiles")
    if not isinstance(profiles_value, list) or not profiles_value:
        raise ValueError("evidence field 'profiles' must be a non-empty array")
    profiles = []
    for profile in profiles_value:
        if not isinstance(profile, str) or not profile.strip():
            raise ValueError("every profile must be a non-empty string")
        profiles.append(profile.strip())

    results_value = evidence.get("results")
    if not isinstance(results_value, list):
        raise ValueError("evidence field 'results' must be an array")
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
        "runner": runner,
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
        "runner": runner,
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
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"evidence insert failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("evidence insert failed because the endpoint was unreachable") from exc

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


def main() -> int:
    args = parse_args()
    try:
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
        print(f"evidence publish failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
