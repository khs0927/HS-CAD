from __future__ import annotations

from pathlib import Path
from typing import Any

from src.execution.xicad_policy_candidate import build_policy_candidates_from_aliases
from src.execution.xicad_policy_loader import load_xicad_alias_policies
from src.integrations.xicad_rule_engine import XiCADRuleEngine
from src.reports.json_exporter import export_json


def render_policy_candidates_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD XiCAD Policy Candidate Report",
        "",
        f"- Source: {report.get('source')}",
        f"- Alias count: {report.get('alias_count')}",
        f"- Existing count: {report.get('existing_count')}",
        f"- Candidate count: {report.get('candidate_count')}",
        f"- Blocked candidate count: {report.get('blocked_candidate_count')}",
        f"- Review required count: {report.get('review_required_count')}",
        "",
        "## Candidates",
    ]
    for item in report.get("candidates") or []:
        lines.append(
            f"- {item.get('alias')} | {item.get('status')} | risk={item.get('suggested_risk')} | {item.get('reason')}"
        )
    lines += [
        "",
        "## Safety",
        "- This report does not approve execution.",
        "- New aliases must be reviewed before promotion.",
        "- allowed_for_execution remains false at this stage.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def run_xicad_policy_candidate_worker(
    *,
    xicad_root: str = "C:/xicad",
    out_dir: str | Path = "outputs/xicad_policy_candidates",
    policy_override_path: str | None = None,
) -> dict[str, Any]:
    engine = XiCADRuleEngine(xicad_root)
    loaded = engine.load_all_rules()

    aliases: dict[str, str] = {}
    aliases.update({str(k).upper(): str(v) for k, v in engine.shortkeys.items()})
    aliases.update({str(k).upper(): str(v) for k, v in engine.pgp_aliases.items()})

    policies = load_xicad_alias_policies(override_path=policy_override_path)
    report = build_policy_candidates_from_aliases(
        aliases,
        source=xicad_root,
        existing_policies=policies,
    )

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    candidates_json = out / "XICAD_POLICY_CANDIDATES.json"
    candidates_md = out / "XICAD_POLICY_CANDIDATES.md"
    effective_policy_json = out / "XICAD_ALIAS_POLICIES_EFFECTIVE.json"

    payload = report.to_dict()
    export_json(payload, candidates_json)
    candidates_md.write_text(render_policy_candidates_markdown(payload), encoding="utf-8")
    export_json(
        {
            "loaded": loaded,
            "xicad_root": xicad_root,
            "policy_count": len(policies),
            "policies": [policy.to_dict() for policy in policies.values()],
        },
        effective_policy_json,
    )

    return {
        "out_dir": str(out),
        "loaded": loaded,
        "alias_count": len(aliases),
        "candidate_count": report.candidate_count,
        "blocked_candidate_count": report.blocked_candidate_count,
        "review_required_count": report.review_required_count,
        "candidates_json": str(candidates_json),
        "candidates_report": str(candidates_md),
        "effective_policy_json": str(effective_policy_json),
    }
