"""Safety policy constants."""
from __future__ import annotations

SAFETY_FLAGS: dict[str, bool] = {
    "main_merge_performed_by_this_bundle": False,
    "local_validation_executed_by_this_bundle": False,
    "final_live_runner_implemented": False,
    "sendcommand_allowed_by_default": False,
    "cad_execution_allowed_by_default": False,
    "zwcad_com_allowed_by_default": False,
    "zwcad_com_sendcommand_allowed": False,
    "xicad_alias_execution_allowed": False,
    "domain_rule_command_execution_allowed": False,
    "original_dwg_mutation_allowed": False,
    "post_main_local_validation_manual_only": True,
    "final_live_runner_requires_separate_safety_spec_pr": True,
}


def assert_safe_defaults() -> None:
    forbidden_true = [k for k, v in SAFETY_FLAGS.items() if k not in {"post_main_local_validation_manual_only", "final_live_runner_requires_separate_safety_spec_pr"} and v]
    if forbidden_true:
        raise RuntimeError(f"Unsafe safety flags enabled: {forbidden_true}")
