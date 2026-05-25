#!/usr/bin/env python3
"""Convenience wrapper for next-stage smoke pipeline."""
from __future__ import annotations

import argparse

from hscad.pipelines.next_stage_pipeline import run_next_stage_pipeline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="tests/fixtures/minimal_floorplan.dxf")
    parser.add_argument("--out", default="outputs/next_stage_smoke")
    args = parser.parse_args()
    result = run_next_stage_pipeline(args.input, args.out)
    print(result["out_dir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
