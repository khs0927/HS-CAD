from __future__ import annotations

from src.modifiers.planned_action_executor import PlannedActionExecutor


class FakeAdapter:
    def __init__(self):
        self.created = []

    @staticmethod
    def safe_get(obj, attr):
        return obj.get(attr)

    def create_line(self, start, end, layer):
        obj = {"Handle": f"L{len(self.created)}"}
        self.created.append(("line", start, end, layer))
        return obj

    def create_polyline(self, points, layer, closed=False):
        obj = {"Handle": f"P{len(self.created)}"}
        self.created.append(("polyline", points, layer, closed))
        return obj


def test_planned_action_executor_records_results() -> None:
    adapter = FakeAdapter()
    result = PlannedActionExecutor(adapter).execute([
        {"action": "create_line", "start": [0, 0, 0], "end": [1, 0, 0], "layer": "A-GRID"},
        {"action": "create_rectangle_placeholder", "points": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], "layer": "A-COLUMN"},
    ])
    assert result["success_count"] == 2
    assert len(adapter.created) == 2
