from __future__ import annotations

from src.ui.view_models import ProjectState


def create_initial_state() -> ProjectState:
    return ProjectState()


if __name__ == "__main__":
    print(create_initial_state())
