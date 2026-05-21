import json
from pathlib import Path

from .schema import MergeCandidatePlan, to_dict


def write_merge_plan_json(plan: MergeCandidatePlan, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(to_dict(plan), ensure_ascii=False, indent=2), encoding="utf-8")


def write_merge_plan_md(plan: MergeCandidatePlan, path: str | Path) -> None:
    lines = [
        "# Merge Candidate Plan",
        "",
        f"- Mode: {plan.mode}",
        f"- Can merge: {plan.can_merge}",
        f"- Requires user approval: {plan.requires_user_approval}",
        f"- Source preview session: {plan.source_preview_session}",
        "",
        "## Merge Groups",
    ]
    for group in plan.merge_groups:
        lines.append(
            f"- {group.group}: action={group.action}, layer={group.target_layer}, confidence={group.confidence}, count={group.count}"
        )
    lines += ["", "## Blocked Actions"]
    for action in plan.blocked_actions:
        lines.append(f"- {action}")
    lines += ["", "## Warnings"]
    for warning in plan.warnings or ["none"]:
        lines.append(f"- {warning}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
