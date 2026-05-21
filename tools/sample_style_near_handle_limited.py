from __future__ import annotations

import argparse
import json
from pathlib import Path

# 이 파일은 기존 tools/sample_style_near_handle.py를 덮어쓰지 않는 성능 제한 래퍼 예시입니다.
# 기존 함수에 max_items 인자가 없는 경우에도 안전하게 실패하도록 별도 파일로 제공합니다.


def main() -> int:
    parser = argparse.ArgumentParser(description="Limited wrapper guidance for sample_style_near_handle.")
    parser.add_argument("--note", action="store_true")
    args = parser.parse_args()
    message = {
        "purpose": "Add --max-items support to tools/sample_style_near_handle.py without changing behavior.",
        "recommended_patch": {
            "function_arg": "max_items: int = 50000",
            "json_fields": ["max_items", "scanned_entity_count", "stopped_early"],
            "cli_arg": "--max-items",
        },
        "reason": "Large DWGs can be slow when ModelSpace is scanned without a limit.",
    }
    print(json.dumps(message, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
