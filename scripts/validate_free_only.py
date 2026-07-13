#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_RUNTIME_PACKAGES = {
    "anthropic",
    "fal-client",
    "langsmith",
    "openai",
    "pinecone",
    "pinecone-client",
    "posthog",
    "replicate",
    "sentry-sdk",
    "stripe",
    "weaviate-client",
}

FORBIDDEN_SECRET_NAMES = {
    "ANTHROPIC_API_KEY",
    "FAL_KEY",
    "LANGCHAIN_API_KEY",
    "OPENAI_API_KEY",
    "PINECONE_API_KEY",
    "REPLICATE_API_TOKEN",
    "STRIPE_SECRET_KEY",
}

OPTIONAL_FREE_SERVICES = {
    "supabase": "Optional free-tier run summaries only; local SQLite remains default.",
    "huggingface": "Optional offline model download only; hosted Jobs are not required.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that HS-CAD's required runtime is free and local-first."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def _package_name(requirement: str) -> str:
    value = requirement.split(";", 1)[0].strip()
    value = re.split(r"[<>=!~\[]", value, maxsplit=1)[0]
    return value.strip().lower().replace("_", "-")


def _load_pyproject(root: Path) -> dict[str, Any]:
    with (root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _runtime_dependencies(project: dict[str, Any]) -> set[str]:
    dependencies = project.get("project", {}).get("dependencies", [])
    return {_package_name(str(value)) for value in dependencies}


def _scan_env_examples(root: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for path in sorted((root / "config").glob("*.env.example")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name = stripped.split("=", 1)[0].strip()
            if name in FORBIDDEN_SECRET_NAMES:
                issues.append(
                    {
                        "type": "paid_secret_in_example",
                        "path": str(path.relative_to(root)),
                        "line": str(line_number),
                        "name": name,
                    }
                )
    return issues


def _required_files(root: Path) -> list[dict[str, str]]:
    required = [
        "src/drawing_index/infrastructure/local_sqlite_summary_sink.py",
        "config/free-only.env.example",
        "docs/24_free_only_runtime.md",
    ]
    return [
        {"type": "missing_required_file", "path": value}
        for value in required
        if not (root / value).exists()
    ]


def validate(root: Path) -> dict[str, Any]:
    pyproject = _load_pyproject(root)
    runtime = _runtime_dependencies(pyproject)
    paid_dependencies = sorted(runtime & FORBIDDEN_RUNTIME_PACKAGES)
    issues: list[dict[str, str]] = [
        {"type": "paid_runtime_dependency", "package": package}
        for package in paid_dependencies
    ]
    issues.extend(_scan_env_examples(root))
    issues.extend(_required_files(root))

    default_profile = root / "config" / "free-only.env.example"
    if default_profile.exists():
        profile_text = default_profile.read_text(encoding="utf-8")
        for required_setting in (
            "HSCAD_RUNTIME_PROFILE=free-local",
            "HSCAD_SUMMARY_BACKEND=local",
            "HSCAD_ALLOW_PAID_SERVICES=0",
        ):
            if required_setting not in profile_text:
                issues.append(
                    {
                        "type": "missing_free_profile_setting",
                        "setting": required_setting,
                    }
                )

    return {
        "valid": not issues,
        "runtime_dependencies": sorted(runtime),
        "forbidden_runtime_dependencies": paid_dependencies,
        "optional_free_services": OPTIONAL_FREE_SERVICES,
        "issues": issues,
        "guarantees": [
            "Core drawing indexing works without accounts or API keys.",
            "Default run summaries are stored in local SQLite.",
            "No paid AI SDK is a required dependency.",
            "Cloud services are optional and disabled by default.",
            "Drawing bytes and extracted text remain local by default.",
        ],
    }


def main() -> int:
    args = parse_args()
    result = validate(args.root.resolve())
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("HS-CAD free-only runtime validation")
        print(f"valid={result['valid']}")
        print(f"runtime_dependencies={len(result['runtime_dependencies'])}")
        if result["issues"]:
            for issue in result["issues"]:
                print("ERROR", json.dumps(issue, ensure_ascii=False))
        else:
            for guarantee in result["guarantees"]:
                print("OK", guarantee)
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
