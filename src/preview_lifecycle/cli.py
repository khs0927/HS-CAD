import argparse
import json
from pathlib import Path

from .manager import create_session_from_plan_and_insert_result, remove_preview, replace_preview
from .report import write_json, write_session_md
from .store import list_preview_sessions, load_preview_session, save_preview_session


def cmd_create_session(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    session = create_session_from_plan_and_insert_result(args.plan, args.insert_result)
    save_preview_session(session, out / "preview_session.json")
    write_session_md(session, out / "preview_session.md")
    print(out / "preview_session.json")
    return 0


def cmd_list_previews(args):
    sessions = list_preview_sessions(args.dir)
    print(json.dumps([str(x) for x in sessions], ensure_ascii=False, indent=2))
    return 0


def cmd_remove_preview(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    session = load_preview_session(args.session)
    result = remove_preview(session, allow_execute=args.allow_execute)
    write_json(result, out / "preview_remove_result.json")
    print(out / "preview_remove_result.json")
    return 0 if not result.errors else 1


def cmd_replace_preview(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    session = load_preview_session(args.session)
    result = replace_preview(session, args.source_dxf, out / "preview_session.json", allow_execute=args.allow_execute)
    write_json(result, out / "preview_replace_result.json")
    print(out / "preview_replace_result.json")
    return 0 if not result.errors else 1


def build_parser():
    parser = argparse.ArgumentParser(description="Manage HS-CAD preview insert sessions.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-session")
    p.add_argument("--plan")
    p.add_argument("--insert-result")
    p.add_argument("--out", default="generated/stage24")
    p.set_defaults(func=cmd_create_session)

    p = sub.add_parser("list-previews")
    p.add_argument("--dir", default="generated/stage24")
    p.set_defaults(func=cmd_list_previews)

    p = sub.add_parser("remove-preview")
    p.add_argument("--session", required=True)
    p.add_argument("--allow-execute", action="store_true")
    p.add_argument("--out", default="generated/stage24")
    p.set_defaults(func=cmd_remove_preview)

    p = sub.add_parser("replace-preview")
    p.add_argument("--session", required=True)
    p.add_argument("--source-dxf", required=True)
    p.add_argument("--allow-execute", action="store_true")
    p.add_argument("--out", default="generated/stage24")
    p.set_defaults(func=cmd_replace_preview)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
