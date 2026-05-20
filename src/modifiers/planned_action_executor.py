from __future__ import annotations

from typing import Any


class PlannedActionExecutor:
    """Execute or preview architectural planned actions through a CAD adapter."""

    def __init__(self, adapter: Any):
        self.adapter = adapter

    @staticmethod
    def preview(actions: list[dict[str, Any]]) -> dict[str, Any]:
        return execute_planned_actions(None, actions, dry_run=True)

    def execute(self, actions: list[dict[str, Any]]) -> dict[str, Any]:
        result = execute_planned_actions(self.adapter, actions, dry_run=False)
        return {
            "executed": True,
            "planned_count": result["planned"],
            "success_count": result["created"],
            "failure_count": len(result["errors"]),
            "results": result["results"],
        }


def execute_planned_actions(adapter: Any, actions: list[dict[str, Any]], dry_run: bool = False) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    created = 0
    errors: list[dict[str, Any]] = []
    for index, action in enumerate(actions):
        kind = action.get("action")
        try:
            if dry_run:
                results.append({"index": index, "action": action, "status": "planned"})
                continue
            if kind == "create_line":
                adapter.create_line(action["start"], action["end"], action.get("layer", "0"))
            elif kind == "create_polyline":
                adapter.create_polyline(action["points"], action.get("layer", "0"), action.get("closed", True))
            elif kind == "insert_block":
                adapter.insert_block(action["block_name"], action["insert"], action.get("layer", "0"), action.get("rotation", 0), action.get("scale", [1, 1, 1]))
            elif kind in {"create_circle_placeholder", "create_circle"}:
                # Placeholder action for future COM implementation.
                if hasattr(adapter, "create_circle"):
                    adapter.create_circle(action["center"], action.get("radius", 250), action.get("layer", "0"))
                else:
                    raise NotImplementedError("Adapter has no create_circle method")
            elif kind in {"create_rectangle_placeholder", "create_rectangle"}:
                adapter.create_polyline(action["points"], action.get("layer", "0"), True)
            elif kind == "set_layer":
                target = adapter._find_by_handle(action["handle"]) if hasattr(adapter, "_find_by_handle") else None
                if target is None:
                    raise ValueError("handle not found")
                target.Layer = action["layer"]
            else:
                raise ValueError(f"Unsupported planned action: {kind}")
            created += 1
            results.append({"index": index, "action": action, "status": "created"})
        except Exception as exc:
            err = {"index": index, "action": action, "error": str(exc)}
            errors.append(err)
            results.append({"index": index, "action": action, "status": "failed", "error": str(exc)})
    return {"created": created, "errors": errors, "planned": len(actions), "results": results, "dry_run": dry_run}
