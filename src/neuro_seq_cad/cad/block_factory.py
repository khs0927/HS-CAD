"""
cad.block_factory – 표준 CAD 블록 정의 (문, 창, 기둥)
======================================================
ezdxf 문서에 DOOR_BLOCK, WINDOW_BLOCK, COLUMN_BLOCK 등
표준 건축 블록을 등록한다.

블록 치수 (단위: mm):
  - 문: 잎(leaf) 900mm, 패널 900mm, 90° 스윙 아크
  - 창: 외곽 1200×200, 내부 유리선 y=50, y=150
  - 기둥: 400×400 정사각 솔리드 해치
"""

from __future__ import annotations

from typing import Any

try:
    import ezdxf
except ImportError:
    ezdxf = None  # type: ignore[assignment]


def create_door_block(doc: Any, name: str = "DOOR_BLOCK") -> None:
    """
    문 블록 생성 — 단일 여닫이(swing) 표현.

    구성 요소:
      1. 문짝(leaf) 선분: (0,0) → (0, 900)
      2. 패널(panel) 선분: (0,0) → (900, 0)
      3. 90° 스윙 아크: 중심=(0,0), 반지름=900

    모든 요소는 DOOR 레이어에 배치된다.
    """
    if ezdxf is None:
        return

    blocks = doc.blocks
    if name in blocks:
        return

    blk = blocks.new(name=name)

    # 문짝 선분 — 힌지에서 위쪽으로 900mm
    blk.add_line(
        start=(0.0, 0.0),
        end=(0.0, 900.0),
        dxfattribs={"layer": "DOOR"},
    )

    # 패널 선분 — 힌지에서 오른쪽으로 900mm
    blk.add_line(
        start=(0.0, 0.0),
        end=(900.0, 0.0),
        dxfattribs={"layer": "DOOR"},
    )

    # 90° 스윙 아크 — 문이 열리는 궤적
    # 시작 각도 0° (양의 X축)에서 90° (양의 Y축)까지
    blk.add_arc(
        center=(0.0, 0.0),
        radius=900.0,
        start_angle=0.0,
        end_angle=90.0,
        dxfattribs={"layer": "DOOR"},
    )


def create_window_block(doc: Any, name: str = "WINDOW_BLOCK") -> None:
    """
    창 블록 생성 — 이중 유리 프레임 표현.

    구성 요소:
      1. 외곽 사각형: 1200×200mm (WIN 레이어)
      2. 내부 유리선 2개: y=50, y=150 (WINBAR 레이어)
    """
    if ezdxf is None:
        return

    blocks = doc.blocks
    if name in blocks:
        return

    blk = blocks.new(name=name)

    # 외곽 프레임 사각형 — WIN 레이어
    blk.add_lwpolyline(
        [(0.0, 0.0), (1200.0, 0.0), (1200.0, 200.0), (0.0, 200.0)],
        dxfattribs={"layer": "WIN"},
        close=True,
    )

    # 내부 유리선 하단 — WINBAR 레이어 (y=50)
    blk.add_line(
        start=(0.0, 50.0),
        end=(1200.0, 50.0),
        dxfattribs={"layer": "WINBAR"},
    )

    # 내부 유리선 상단 — WINBAR 레이어 (y=150)
    blk.add_line(
        start=(0.0, 150.0),
        end=(1200.0, 150.0),
        dxfattribs={"layer": "WINBAR"},
    )


def create_column_block(doc: Any, name: str = "COLUMN_BLOCK") -> None:
    """
    기둥 블록 생성 — 400×400mm 정사각 솔리드.

    구성 요소:
      1. 외곽 사각형 (COL 레이어)
      2. 솔리드 해치 (COL 레이어)
    """
    if ezdxf is None:
        return

    blocks = doc.blocks
    if name in blocks:
        return

    blk = blocks.new(name=name)

    # 외곽 사각형
    blk.add_lwpolyline(
        [(0.0, 0.0), (400.0, 0.0), (400.0, 400.0), (0.0, 400.0)],
        dxfattribs={"layer": "COL"},
        close=True,
    )

    # 솔리드 해치 채우기
    try:
        hatch = blk.add_hatch(dxfattribs={"layer": "COL"})
        hatch.paths.add_polyline_path(
            [(0.0, 0.0), (400.0, 0.0), (400.0, 400.0), (0.0, 400.0)],
            is_closed=True,
        )
    except Exception:
        pass  # 해치 생성 실패 시 무시 (외곽선만 유지)


def create_all_blocks(doc: Any) -> None:
    """
    모든 표준 건축 블록을 ezdxf 문서에 등록.

    호출 순서에 상관없이 중복 생성을 방지한다.
    """
    create_door_block(doc)
    create_window_block(doc)
    create_column_block(doc)
