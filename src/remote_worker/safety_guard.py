from __future__ import annotations

from src.remote_worker.job_schema import RemoteDxfJob

BANNED_ACTIONS = {
    "delete",
    "erase",
    "move",
    "scale",
    "trim",
    "stretch",
    "explode",
    "save_original",
    "overwrite",
}


def validate_job_safety(job: RemoteDxfJob) -> list[str]:
    findings: list[str] = []
    for index, action in enumerate(job.actions):
        if action.type in BANNED_ACTIONS:
            raise ValueError(f"banned action at index {index}: {action.type}")
        if action.type in {"add_text_note", "add_leader_note"}:
            if not action.text:
                raise ValueError(f"{action.type} requires text")
            if action.position is None:
                raise ValueError(f"{action.type} requires position")
            if action.type == "add_leader_note" and action.leader_to is None:
                raise ValueError("add_leader_note requires leader_to")
        if action.type in {"ensure_layer", "normalize_layer_color"} and not action.layer:
            raise ValueError(f"{action.type} requires layer")
        findings.append(f"safe:{index}:{action.type}")
    return findings
