import json
from collections import Counter
from pathlib import Path

from .safety import default_blocked_actions
from .schema import MergeCandidatePlan, MergeGroup


def _load_json(path: str | Path | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_merge_candidate_plan(
    preview_session_path: str | Path | None,
    style_context_path: str | Path | None,
    styled_result_path: str | Path | None,
) -> MergeCandidatePlan:
    session = _load_json(preview_session_path)
    styled = _load_json(styled_result_path)
    context = _load_json(style_context_path)

    plan = MergeCandidatePlan(
        can_merge=False,
        requires_user_approval=True,
        source_preview_session=str(preview_session_path or ""),
        blocked_actions=default_blocked_actions(),
        metadata={"style_context_loaded": bool(context), "styled_result_loaded": bool(styled)},
    )

    if not session:
        plan.warnings.append("preview_session missing or invalid")
    if not styled:
        plan.warnings.append("styled_result missing or invalid")
        return plan

    counts: Counter[tuple[str, str | None]] = Counter()
    confidence_sum: Counter[str] = Counter()
    for item in styled.get("entities", []):
        original = item.get("original_entity") or {}
        group = str(original.get("entity_type") or "unknown")
        layer = item.get("target_layer")
        counts[(group, layer)] += 1
        confidence_sum[group] += float(item.get("style_confidence") or original.get("confidence") or 0.5)

    for (group, layer), count in counts.items():
        total = sum(v for (g, _), v in counts.items() if g == group)
        avg_conf = confidence_sum[group] / max(total, 1)
        action = "review_before_merge" if avg_conf < 0.85 or layer in {"AI_LOWCONF", "QA-REVIEW"} else "candidate_after_review"
        plan.merge_groups.append(
            MergeGroup(group=group, action=action, target_layer=layer, confidence=round(avg_conf, 4), count=count)
        )

    plan.warnings.append("Stage 24 creates a merge candidate plan only; it does not merge into DWG.")
    return plan
