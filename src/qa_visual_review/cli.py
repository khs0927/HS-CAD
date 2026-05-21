import argparse
from pathlib import Path

from .builder import build_qa_markup
from .report import write_qa_json, write_qa_md


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build QA markup/review report from styled neuro result.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build-review")
    p.add_argument("--styled-result")
    p.add_argument("--preview-session")
    p.add_argument("--out", default="generated/stage24")
    args = parser.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    markup = build_qa_markup(args.styled_result, args.preview_session)
    write_qa_json(markup, out / "qa_markup.json")
    write_qa_md(markup, out / "qa_review_report.md")
    print(out / "qa_review_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
