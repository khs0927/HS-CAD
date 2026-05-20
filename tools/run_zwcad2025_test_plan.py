from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.run_zwcad_test_plan import main as common_main


if __name__ == "__main__":
    if "--version" not in sys.argv:
        sys.argv[1:1] = ["--version", "2025"]
    if "--out-dir" not in sys.argv:
        sys.argv.extend(["--out-dir", "outputs/zwcad2025_test_plan"])
    common_main()
