from __future__ import annotations

import math
from pathlib import Path

from neuro_seq_cad.line_extraction.hough import extract_hough_lines
from neuro_seq_cad.line_extraction.raw_line_schema import RawLine, RawLineResult


def extract_raw_lines(image_path: str | Path) -> RawLineResult:
    """Extract raw line candidates and keep every candidate for RAW_LINES."""

    try:
        import cv2  # type: ignore

        img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return extract_hough_lines(image_path)
        detector = cv2.createLineSegmentDetector()
        detected = detector.detect(img)[0]
        if detected is None:
            return extract_hough_lines(image_path)
        lines: list[RawLine] = []
        for i, item in enumerate(detected[:500]):
            x1, y1, x2, y2 = [float(v) for v in item[0]]
            dx = x2 - x1
            dy = y2 - y1
            length = math.hypot(dx, dy)
            if length < 20:
                continue
            lines.append(
                RawLine(
                    id=f"line_{i:04d}",
                    p1=[x1, y1],
                    p2=[x2, y2],
                    angle=math.degrees(math.atan2(dy, dx)),
                    length=length,
                    confidence=0.78,
                    source="opencv_lsd",
                )
            )
        return RawLineResult(lines=lines or extract_hough_lines(image_path).lines)
    except Exception:
        return extract_hough_lines(image_path)

