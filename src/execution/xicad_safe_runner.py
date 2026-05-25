from __future__ import annotations

from typing import Any

from src.execution.xicad_alias_classifier import classify_xicad_alias
from src.execution.xicad_policy_loader import load_xicad_alias_policies


class XiCADSafeRunnerBlocked(RuntimeError):
    pass


class XiCADSafeRunner:
    def __init__(self, *, adapter: Any | None = None, policy_override_path: str | None = None):
        self.adapter = adapter
        self.policies = load_xicad_alias_policies(override_path=policy_override_path)

    def dry_run_alias(self, alias_or_hint: str) -> dict[str, Any]:
        classification = classify_xicad_alias(alias_or_hint, policies=self.policies)

        if not classification.allowed_for_dry_run:
            return {
                "status": "blocked",
                "alias": classification.alias,
                "reason": classification.blocked_reason or "Alias is not allowed for dry-run.",
                "classification": classification.to_dict(),
                "executed": False,
            }

        return {
            "status": "dry_run_recorded",
            "alias": classification.alias,
            "classification": classification.to_dict(),
            "executed": False,
            "would_send_command": False,
            "message": "XiCAD alias dry-run recorded. No command was executed.",
        }

    def execute_alias(self, alias_or_hint: str) -> dict[str, Any]:
        classification = classify_xicad_alias(alias_or_hint, policies=self.policies)

        raise XiCADSafeRunnerBlocked(
            f"XiCAD alias execution is not enabled in this PR. Alias={classification.alias}"
        )
