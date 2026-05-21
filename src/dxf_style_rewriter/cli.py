import argparse

from .rewriter import rewrite_dxf


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Rewrite/copy image-to-CAD DXF using HS-CAD style context.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("rewrite-dxf")
    p.add_argument("--source-dxf", required=True)
    p.add_argument("--styled-result")
    p.add_argument("--style-context")
    p.add_argument("--out", default="generated/stage24")

    args = parser.parse_args(argv)
    if args.command == "rewrite-dxf":
        report = rewrite_dxf(args.source_dxf, args.styled_result, args.style_context, args.out)
        print(report.output_dxf or "no output")
        return 0 if not report.errors else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
