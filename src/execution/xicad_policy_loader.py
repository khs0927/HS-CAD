from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.execution.xicad_alias_policy import (
    XiCADAliasPolicy,
    build_default_xicad_alias_policies,
)


def load_xicad_alias_policies(
    *,
    override_path: str | Path | None = None,
    force_no_execution: bool = True,
) -> dict[str, XiCADAliasPolicy]:
    policies = dict(build_default_xicad_alias_policies())

    default_override = Path("config/xicad_alias_policy_overrides.json")
    paths: list[Path] = []
    if default_override.exists():
        paths.append(default_override)
    if override_path:
        paths.append(Path(override_path))

    for path in paths:
        policies.update(_load_policy_file(path, force_no_execution=force_no_execution))

    return policies


def _load_policy_file(path: Path, *, force_no_execution: bool) -> dict[str, XiCADAliasPolicy]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "policies" in data:
        rows = data["policies"]
    elif isinstance(data, list):
        rows = data
    else:
        raise ValueError(f"Unsupported XiCAD alias policy file shape: {path}")

    out: dict[str, XiCADAliasPolicy] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue

        alias = str(row.get("alias") or "").upper()
        if not alias:
            continue

        allowed_for_execution = bool(row.get("allowed_for_execution", False))
        if force_no_execution:
            allowed_for_execution = False

        policy = XiCADAliasPolicy(
            alias=alias,
            risk=str(row.get("risk") or "review_required"),  # type: ignore[arg-type]
            title=str(row.get("title") or f"Policy for {alias}"),
            description=str(row.get("description") or ""),
            allowed_for_dry_run=bool(row.get("allowed_for_dry_run", True)),
            allowed_for_execution=allowed_for_execution,
            requires_human_review=bool(row.get("requires_human_review", True)),
            destructive=bool(row.get("destructive", False)),
            tags=list(row.get("tags") or []),
            notes=list(row.get("notes") or []),
        )
        out[alias] = policy
    return out
