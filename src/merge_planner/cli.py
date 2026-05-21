import argparse
from pathlib import Path

from .builder import build_merge_candidate_plan
from .report import write_merge_plan_json, write_merge_plan_md


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build plan-only merge candidate report.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build-merge-candidate")
    p.add_argument("--preview-session")
    p.add_argument("--style-context")
    p.add_argument("--styled-result")
    p.add_argument("--out", default="generated/stage24")
    args = parser.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plan = build_merge_candidate_plan(args.preview_session, args.style_context, args.styled_result)
    write_merge_plan_json(plan, out / "merge_candidate_plan.json")
    write_merge_plan_md(plan, out / "merge_candidate_report.md")
    print(out / "merge_candidate_plan.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
