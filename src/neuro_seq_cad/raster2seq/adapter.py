"""
adapter.py — Raster2Seq AI 모델 서브프로세스 래퍼 및 어댑터

도면 이미지로부터 다각형 세그먼트 시퀀스(방, 벽 등)를 검출하는
Raster2Seq 저장소(external)를 호출하고 추론 결과를 파싱하는 어댑터 클래스입니다.
로컬에 모델 가중치(Checkpoint)가 없거나 실행 환경이 갖춰지지 않은 경우를 대비하여
스마트한 모의 데이터 생성(Graceful Mock Fallback)을 지원합니다.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from neuro_seq_cad.config.settings import get_settings
from neuro_seq_cad.raster2seq.polygon_schema import Raster2SeqOutput, PolygonResult
from neuro_seq_cad.raster2seq.sequence_parser import parse_polygon_sequence

logger = logging.getLogger(__name__)


class Raster2SeqAdapter:
    """Raster2Seq 딥러닝 모델 실행 및 결과 융합을 위한 어댑터."""

    def __init__(
        self,
        raster2seq_dir: Optional[Path] = None,
        checkpoint_path: Optional[Path] = None,
        dataset: str = "cubicasa"
    ) -> None:
        settings = get_settings()
        self.raster2seq_dir = raster2seq_dir or settings.raster2seq_dir
        self.checkpoint_path = checkpoint_path or settings.raster2seq_checkpoint
        self.dataset = dataset

    def is_available(self) -> bool:
        """Raster2Seq 모듈을 실제로 구동할 수 있는지 여부를 점검합니다."""
        # 1. 외부 소스 디렉토리 존재 확인
        if not self.raster2seq_dir.exists():
            return False
            
        # 2. 추론 핵심 스크립트 존재 확인
        predict_script = self.raster2seq_dir / "predict.py"
        if not predict_script.exists():
            return False
            
        # 3. 모델 가중치 체크포인트 파일 확인
        if not self.checkpoint_path.exists():
            return False
            
        return True

    def predict(
        self,
        image_path: Path,
        output_dir: Optional[Path] = None
    ) -> Raster2SeqOutput:
        """도면 이미지에 대해 Raster2Seq 모델을 적용하여 다각형 목록을 추출합니다.

        만약 모델 환경이 로드되지 않은 상태라면 dummy_predict()를 호출하여 모의 결과를 반환합니다.
        """
        image_path = Path(image_path).resolve()
        if not image_path.exists():
            raise FileNotFoundError(f"추론할 이미지가 없습니다: {image_path}")
            
        if not self.is_available():
            logger.warning(
                "Raster2Seq 가중치 또는 리포지토리가 유효하지 않습니다. "
                "실물 모델 추론을 건너뛰고 Graceful Mock Fallback을 실행합니다."
            )
            return self._predict_mock(image_path)
            
        settings = get_settings()
        out_dir = output_dir or settings.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Raster2Seq 실물 모델 추론 시작: image=%s", image_path.name)
        
        # 외부 리포지토리의 predict.py 실행
        # 명령행 옵션: python predict.py --ckpt_path <> --img_dir <> --save_dir <> --dataset <>
        # Raster2Seq는 폴더 내 전체 이미지를 처리하므로 임시 폴더에 타겟 이미지만 복사해 넣는 편이 안전합니다.
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # 이미지 파일 링크 또는 복사
            tmp_image = tmp_path / image_path.name
            try:
                import shutil
                shutil.copy(image_path, tmp_image)
            except Exception as e:
                logger.error("이미지 복사 실패: %s", e)
                return self._predict_mock(image_path)
                
            cmd = [
                "python",
                str(self.raster2seq_dir / "predict.py"),
                "--ckpt_path", str(self.checkpoint_path),
                "--img_dir", str(tmp_path),
                "--save_dir", str(out_dir),
                "--dataset", self.dataset,
                "--device", settings.device
            ]
            
            try:
                logger.debug("실행 명령: %s", " ".join(cmd))
                res = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    cwd=str(self.raster2seq_dir)
                )
                logger.debug("추론 출력: %s", res.stdout)
            except subprocess.CalledProcessError as err:
                logger.error("Raster2Seq 실행 오류! stderr: %s", err.stderr)
                return self._predict_mock(image_path)
                
            # 출력 디렉토리에서 이미지 파일명에 대응하는 JSON 파일 로드
            # 예측 결과는 통상 [이미지파일명]_pred.json 등의 형태로 저장됩니다.
            stem = image_path.stem
            expected_json = out_dir / f"{stem}_pred.json"
            
            # 파일이 없을 시, 해당 확장자를 포함한 매칭 확인
            if not expected_json.exists():
                expected_json = out_dir / f"{image_path.name}_pred.json"
                
            if expected_json.exists():
                try:
                    with open(expected_json, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                    return parse_polygon_sequence(raw_data)
                except Exception as e:
                    logger.error("Raster2Seq 출력 JSON 파일 파싱 에러: %s", e)
                    return self._predict_mock(image_path)
            else:
                logger.warning("Raster2Seq 출력 결과 파일 없음. Mock으로 Fallback합니다.")
                return self._predict_mock(image_path)

    def _predict_mock(self, image_path: Path) -> Raster2SeqOutput:
        """가중치가 없는 환경에서 실감나는 목업 다각형 레이아웃을 생성합니다.

        기본 사각형 벽체 바운더리와 안쪽에 세 개의 방(Bedroom, Kitchen, Living Room)을 나누어 구성합니다.
        테스트 환경에서 실질적으로 geometry Snap/Merge 및 DXF 생성을 검증하기 위해 기하 좌표를 실감나게 잡습니다.
        """
        logger.info("Mock Raster2Seq 결과를 생성합니다. (대상: %s)", image_path.name)
        
        # 이미지 크기를 추정하여 기하 중심을 잡습니다.
        # 실제 이미지가 있으면 Pillow로 크기를 읽어옵니다.
        width, height = 1200, 800
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                width, height = img.size
        except Exception:
            pass
            
        polygons = []
        
        # 1. 외곽 벽체 경계선 (Wall Boundary)
        # 이미지 마진 50px
        x1, y1 = 50.0, 50.0
        x2, y2 = float(width - 50), float(height - 50)
        
        wall_pts = [
            [x1, y1], [x2, y1], [x2, y2], [x1, y2]
        ]
        polygons.append(PolygonResult(
            type="wall_boundary",
            label="Wall",
            points=wall_pts,
            confidence=0.95,
            source="raster2seq_mock"
        ))
        
        # 2. 방 분할 (3개 구역)
        # 가로 절반 기준 좌우 분할, 왼쪽방은 다시 세로 절반 분할
        mx = (x1 + x2) / 2.0
        my = (y1 + y2) / 2.0
        
        # Room 1: Bedroom (좌상단)
        polygons.append(PolygonResult(
            type="room",
            label="Bedroom",
            points=[[x1, y1], [mx, y1], [mx, my], [x1, my]],
            confidence=0.92,
            source="raster2seq_mock"
        ))
        
        # Room 2: Bath (좌하단)
        polygons.append(PolygonResult(
            type="room",
            label="Bath",
            points=[[x1, my], [mx, my], [mx, y2], [x1, y2]],
            confidence=0.88,
            source="raster2seq_mock"
        ))
        
        # Room 3: Living Room (우측 전체)
        polygons.append(PolygonResult(
            type="room",
            label="Living Room",
            points=[[mx, y1], [x2, y1], [x2, y2], [mx, y2]],
            confidence=0.90,
            source="raster2seq_mock"
        ))
        
        # 3. 문 (Doors) - 방 사이 및 현관
        # 현관문 (Living Room 우측벽 아래)
        polygons.append(PolygonResult(
            type="door",
            label="Door",
            points=[[x2 - 5, y2 - 150], [x2 + 5, y2 - 150], [x2 + 5, y2 - 50], [x2 - 5, y2 - 50]],
            confidence=0.85,
            source="raster2seq_mock"
        ))
        
        # Bedroom 문 (Bedroom 하단벽 중앙 부근)
        bx_mid = (x1 + mx) / 2.0
        polygons.append(PolygonResult(
            type="door",
            label="Door",
            points=[[bx_mid - 40, my - 5], [bx_mid + 40, my - 5], [bx_mid + 40, my + 5], [bx_mid - 40, my + 5]],
            confidence=0.82,
            source="raster2seq_mock"
        ))
        
        # 4. 창문 (Windows) - 외곽벽
        # Living Room 큰 창 (우측벽 중앙)
        polygons.append(PolygonResult(
            type="window",
            label="Window",
            points=[[x2 - 5, y1 + 100], [x2 + 5, y1 + 100], [x2 + 5, y2 - 250], [x2 - 5, y2 - 250]],
            confidence=0.84,
            source="raster2seq_mock"
        ))
        
        # Bedroom 창 (상단벽 중앙)
        polygons.append(PolygonResult(
            type="window",
            label="Window",
            points=[[bx_mid - 80, y1 - 5], [bx_mid + 80, y1 - 5], [bx_mid + 80, y1 + 5], [bx_mid - 80, y1 + 5]],
            confidence=0.87,
            source="raster2seq_mock"
        ))
        
        return Raster2SeqOutput(polygons=polygons)
