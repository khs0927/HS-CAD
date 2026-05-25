from __future__ import annotations


from src.extensions.xicad_safe_bridge import (
    XicadSafeCommand,
    XicadSafePlanner,
    default_xicad_registry,
)


def test_default_registry_contains_core_architecture_aliases():
    registry = default_xicad_registry()
    for alias in ["WAL", "COL", "D1", "W1", "PK", "STP", "ELV", "INS"]:
        assert registry.get(alias) is not None


def test_unknown_alias_is_rejected():
    registry = default_xicad_registry()
    planner = XicadSafePlanner(registry)
    command = XicadSafeCommand(command="xicad_safe_plan", alias="NOT_REAL")
    try:
        planner.build_plan(command)
    except ValueError as exc:
        assert "unknown" in str(exc).lower() or "not allowed" in str(exc).lower()
    else:
        raise AssertionError("Unknown alias should be rejected")


def test_interactive_command_is_blocked_by_default():
    registry = default_xicad_registry()
    planner = XicadSafePlanner(registry)
    command = XicadSafeCommand(command="xicad_safe_plan", alias="WAL")
    plan = planner.build_plan(command)

    assert plan.alias == "WAL"
    assert plan.can_execute is False
    assert plan.interactive_required is True
    assert plan.warnings


def test_interactive_command_can_be_planned_for_execution_when_allowed_and_not_dry_run():
    registry = default_xicad_registry()
    planner = XicadSafePlanner(registry)
    command = XicadSafeCommand.model_validate(
        {
            "command": "xicad_safe_execute",
            "alias": "WAL",
            "dry_run": False,
            "safety": {
                "backup_required": True,
                "preview_required": True,
                "allow_interactive": True,
                "allow_high_risk": False,
            },
        }
    )
    plan = planner.build_plan(command)

    assert plan.can_execute is True
    assert "WAL" in plan.commands_to_send


def test_example_safe_command_json_is_valid():
    raw = {
        "command": "xicad_safe_plan",
        "alias": "COL",
        "load_first": True,
        "dry_run": True,
        "params": {"note": "preview only"},
        "safety": {"backup_required": True, "preview_required": True},
    }
    command = XicadSafeCommand.model_validate(raw)
    assert command.alias == "COL"
