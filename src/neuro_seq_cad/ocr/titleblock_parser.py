from __future__ import annotations

import re


def extract_scale_texts(texts: list[str]) -> list[str]:
    return [text for text in texts if re.search(r"1\s*[:/]\s*\d+", text)]

