"""
sequence_parser.py – Raster2Seq 모델의 원시 JSON 출력을 PolygonResult 객체로 변환.

Raster2Seq는 데이터셋(cubicasa, s3d, r2g)에 따라 서로 다른 JSON 형식을
출력한다.  이 모듈은 각 형식을 파싱하여 통일된 PolygonResult 리스트로 변환.
"""
from __future__ import annotations

import logging
from typing import Any

from .polygon_schema import LABEL_TO_TYPE, PolygonResult

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# 데이터셋별 라벨 매핑 보조 테이블
# ──────────────────────────────────────────────────────────────────────

# CubiCasa5K 라벨 인덱스 → 라벨 이름 (공식 데이터셋 기준)
CUBICASA_LABEL_MAP: dict[int, str] = {
    0:  "Background",
    1:  "Outdoor",
    2:  "Wall",
    3:  "Kitchen",
    4:  "Living Room",
    5:  "Bedroom",
    6:  "Bath",
    7:  "Hallway",
    8:  "Door",
    9:  "Window",
    10: "Closet",
    11: "Balcony",
    12: "Corridor",
    13: "Dining Room",
    14: "Stairs",
    15: "Storage",
    16: "Garage",
}

# S3D (Structured3D) 라벨 인덱스 → 라벨 이름
S3D_LABEL_MAP: dict[int, str] = {
    0:  "Background",
    1:  "Living Room",
    2:  "Kitchen",
    3:  "Bedroom",
    4:  "Bathroom",
    5:  "Balcony",
    6:  "Corridor",
    7:  "Dining Room",
    8:  "Study",
    9:  "Studio",
    10: "Storage",
    11: "Wall",
    12: "Door",
    13: "Window",
}

# R2G (Raster2Graph) – 대부분 CubiCasa 동일 구조이므로 fallback 사용
R2G_LABEL_MAP: dict[int, str] = CUBICASA_LABEL_MAP.copy()


def _resolve_label(
    raw_label: str | int,
    dataset: str = "cubicasa",
) -> tuple[str, str]:
    """원시 라벨 값을 (label, type) 튜플로 정규화.

    Args:
        raw_label: 모델 출력의 원시 라벨 (문자열 또는 정수 인덱스).
        dataset: 데이터셋 이름 ("cubicasa" | "s3d" | "r2g").

    Returns:
        (label, type) 튜플.  예: ("Bedroom", "room")
    """
    # 정수 인덱스인 경우 데이터셋별 맵으로 문자열 변환
    if isinstance(raw_label, int):
        label_maps: dict[str, dict[int, str]] = {
            "cubicasa": CUBICASA_LABEL_MAP,
            "s3d": S3D_LABEL_MAP,
            "r2g": R2G_LABEL_MAP,
        }
        lmap = label_maps.get(dataset, CUBICASA_LABEL_MAP)
        label_name = lmap.get(raw_label, "Unknown")
    else:
        label_name = str(raw_label)

    # 라벨 → 타입 매핑
    poly_type = LABEL_TO_TYPE.get(label_name, "unknown")
    return label_name, poly_type


# ──────────────────────────────────────────────────────────────────────
# CubiCasa 형식 파서
# ──────────────────────────────────────────────────────────────────────
def _parse_cubicasa_format(raw_json: dict[str, Any]) -> list[PolygonResult]:
    """CubiCasa 형식 JSON 파싱.

    기대 구조 (예시):
    {
      "polygons": [
        {
          "type": "Bedroom",
          "points": [[x1,y1], [x2,y2], ...],
          "confidence": 0.95
        },
        ...
      ]
    }
    또는 리스트 형태:
    [
      {"type": "Bedroom", "points": [[x1,y1], ...], "confidence": 0.95},
      ...
    ]
    """
    results: list[PolygonResult] = []

    # 딕셔너리 내부에 "polygons" 키가 있는 경우
    items: list[dict[str, Any]] = []
    if isinstance(raw_json, dict):
        items = raw_json.get("polygons", raw_json.get("predictions", []))
        # 만약 items 가 여전히 비어있고 키가 하나뿐이면 그 값을 시도
        if not items:
            for key in raw_json:
                val = raw_json[key]
                if isinstance(val, list) and len(val) > 0:
                    items = val
                    break
    elif isinstance(raw_json, list):
        items = raw_json

    for item in items:
        if not isinstance(item, dict):
            continue

        raw_label = item.get("type", item.get("label", item.get("class", "Unknown")))
        label_name, poly_type = _resolve_label(raw_label, "cubicasa")

        # 좌표 추출 – "points" 또는 "vertices" 키 지원
        raw_points = item.get("points", item.get("vertices", []))
        points: list[list[float]] = []
        for pt in raw_points:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                points.append([float(pt[0]), float(pt[1])])

        confidence = float(item.get("confidence", item.get("score", 0.0)))

        if not points:
            logger.debug("좌표 없는 다각형 건너뜀: label=%s", label_name)
            continue

        results.append(
            PolygonResult(
                type=poly_type,
                label=label_name,
                points=points,
                confidence=confidence,
                source="raster2seq",
            )
        )

    return results


# ──────────────────────────────────────────────────────────────────────
# S3D 형식 파서
# ──────────────────────────────────────────────────────────────────────
def _parse_s3d_format(raw_json: dict[str, Any]) -> list[PolygonResult]:
    """Structured3D (S3D) 형식 JSON 파싱.

    S3D 는 종종 {"rooms": [...], "walls": [...], "openings": [...]} 구조.
    """
    results: list[PolygonResult] = []

    # 방 (rooms)
    for room in raw_json.get("rooms", []):
        label_raw = room.get("type", room.get("label", "Room"))
        label_name, poly_type = _resolve_label(label_raw, "s3d")
        points = _extract_points(room)
        confidence = float(room.get("confidence", room.get("score", 0.0)))
        if points:
            results.append(
                PolygonResult(
                    type=poly_type,
                    label=label_name,
                    points=points,
                    confidence=confidence,
                    source="raster2seq",
                )
            )

    # 벽 (walls)
    for wall in raw_json.get("walls", []):
        points = _extract_points(wall)
        confidence = float(wall.get("confidence", wall.get("score", 0.0)))
        if points:
            results.append(
                PolygonResult(
                    type="wall_boundary",
                    label="Wall",
                    points=points,
                    confidence=confidence,
                    source="raster2seq",
                )
            )

    # 개구부 – 문/창문 (openings)
    for opening in raw_json.get("openings", raw_json.get("doors_windows", [])):
        label_raw = opening.get("type", opening.get("label", "Door"))
        label_name, poly_type = _resolve_label(label_raw, "s3d")
        points = _extract_points(opening)
        confidence = float(opening.get("confidence", opening.get("score", 0.0)))
        if points:
            results.append(
                PolygonResult(
                    type=poly_type,
                    label=label_name,
                    points=points,
                    confidence=confidence,
                    source="raster2seq",
                )
            )

    # fallback: 범용 'polygons' 키가 있으면 CubiCasa 방식으로 처리
    if not results and "polygons" in raw_json:
        results = _parse_cubicasa_format(raw_json)

    return results


# ──────────────────────────────────────────────────────────────────────
# R2G 형식 파서
# ──────────────────────────────────────────────────────────────────────
def _parse_r2g_format(raw_json: dict[str, Any]) -> list[PolygonResult]:
    """Raster2Graph (R2G) 형식 JSON 파싱.

    R2G 출력은 대부분 CubiCasa 와 동일한 구조를 따르지만,
    그래프 노드/엣지 표현이 포함될 수 있음.
    """
    results: list[PolygonResult] = []

    # 그래프 형식: nodes + edges → 다각형 재구성
    if "nodes" in raw_json and "edges" in raw_json:
        nodes = raw_json["nodes"]
        edges = raw_json["edges"]
        # 노드 ID → 좌표 매핑
        node_coords: dict[int | str, list[float]] = {}
        for node in nodes:
            nid = node.get("id", node.get("node_id"))
            x = float(node.get("x", 0.0))
            y = float(node.get("y", 0.0))
            if nid is not None:
                node_coords[nid] = [x, y]

        # 엣지 기반 다각형 구성 – 단순히 연결 리스트로 취급
        for edge in edges:
            src = edge.get("source", edge.get("from"))
            dst = edge.get("target", edge.get("to"))
            p1 = node_coords.get(src)
            p2 = node_coords.get(dst)
            if p1 and p2:
                label_raw = edge.get("type", edge.get("label", "Wall"))
                label_name, poly_type = _resolve_label(label_raw, "r2g")
                results.append(
                    PolygonResult(
                        type=poly_type,
                        label=label_name,
                        points=[p1, p2],
                        confidence=float(edge.get("confidence", 0.0)),
                        source="raster2seq",
                    )
                )
        return results

    # 그래프 형식이 아니면 CubiCasa 형식으로 fallback
    return _parse_cubicasa_format(raw_json)


# ──────────────────────────────────────────────────────────────────────
# 유틸 함수
# ──────────────────────────────────────────────────────────────────────
def _extract_points(item: dict[str, Any]) -> list[list[float]]:
    """아이템 딕셔너리에서 좌표 리스트를 추출.

    'points', 'vertices', 'polygon', 'coords' 키를 순서대로 탐색.
    """
    for key in ("points", "vertices", "polygon", "coords"):
        raw = item.get(key)
        if raw and isinstance(raw, list):
            points: list[list[float]] = []
            for pt in raw:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    points.append([float(pt[0]), float(pt[1])])
            if points:
                return points
    return []


# ──────────────────────────────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────────────────────────────
def parse_polygon_sequence(
    raw_json: dict[str, Any],
    dataset: str = "cubicasa",
) -> list[PolygonResult]:
    """원시 JSON 출력을 PolygonResult 리스트로 파싱.

    데이터셋 종류에 따라 적절한 파서를 선택하여 호출한다.

    Args:
        raw_json: Raster2Seq predict.py 가 출력한 JSON (dict).
        dataset: 데이터셋 이름 – "cubicasa" (기본값), "s3d", "r2g".

    Returns:
        파싱된 PolygonResult 객체 리스트.  파싱 실패 시 빈 리스트.
    """
    parsers = {
        "cubicasa": _parse_cubicasa_format,
        "s3d": _parse_s3d_format,
        "r2g": _parse_r2g_format,
    }

    parser_fn = parsers.get(dataset, _parse_cubicasa_format)

    try:
        results = parser_fn(raw_json)
        logger.info(
            "Raster2Seq 파싱 완료: dataset=%s, 다각형 %d개 검출",
            dataset,
            len(results),
        )
        return results
    except Exception:
        logger.exception("Raster2Seq JSON 파싱 실패: dataset=%s", dataset)
        return []
