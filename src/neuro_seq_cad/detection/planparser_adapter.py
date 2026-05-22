"""
planparser_adapter.py — PlanParser(YOLO / Faster-RCNN 기반 심볼 검출기) 연동을 위한 어댑터

도면 상의 문, 창문, 텍스트, 가구, 기둥 등의 심볼 인스턴스를 탐지합니다.
이 어댑터는 FastAPI 호스트로 구축된 API 연동 방식(detect_api)과
로컬에서 ultralytics 모델을 로드하여 기동하는 로컬 추론 방식(detect_local)을 모두 지원합니다.
최종적으로 두 경로가 모두 실패할 시, 전체 파이프라인의 통합 테스트가 막힘없이 실행되도록
Raster2SeqMock의 기하 좌표와 밀접하게 조화되는 모의 심볼 검출 결과(Mock Fallback)를 생성합니다.

라이선스 고지:
==========================================================================
PlanParser는 Ultralytics YOLOv8/v11 모델을 내부에서 활용하므로,
상업적 용도 사용 시 AGPL-3.0 라이선스 규약 또는 상업적 라이선스 획득에 유의해야 합니다.
==========================================================================
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import requests
from neuro_seq_cad.config.settings import get_settings
from neuro_seq_cad.detection.symbol_schema import DetectionOutput, SymbolDetection

logger = logging.getLogger(__name__)


class PlanParserAdapter:
    """PlanParser AI 심볼 검출기 연동 클래스."""

    def __init__(
        self,
        planparser_dir: Optional[Path] = None,
        api_url: Optional[str] = None
    ) -> None:
        settings = get_settings()
        self.planparser_dir = planparser_dir or settings.planparser_dir
        self.api_url = api_url or settings.planparser_url
        
    def is_available(self) -> bool:
        """API 서버가 활성화되어 있거나 로컬 ultralytics 라이브러리 및 모델이 있는지 확인합니다."""
        # 1. API 서버 핑 테스트
        try:
            # 타임아웃을 짧게 주어 블로킹을 막습니다.
            # 서버가 켜져 있는지 확인하기 위해 GET 요청을 보냅니다 (서버 루트 또는 헬스체크).
            base_url = self.api_url.rsplit("/predict", 1)[0]
            resp = requests.get(base_url, timeout=1.0)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
            
        # 2. 로컬 실행 가능 여부 (ultralytics 설치 여부 및 externals 폴더 확인)
        try:
            import ultralytics
            if self.planparser_dir.exists():
                # 대표 모델 가중치 파일(예: best.pt) 존재 탐색
                weights = list(self.planparser_dir.glob("**/*.pt"))
                if weights:
                    return True
        except ImportError:
            pass
            
        return False

    def detect(self, image_path: Path) -> DetectionOutput:
        """심볼 검출을 수행합니다. API -> 로컬 순으로 시도하며, 모두 실패 시 Mock 결과를 제공합니다."""
        image_path = Path(image_path).resolve()
        if not image_path.exists():
            raise FileNotFoundError(f"탐지 대상 이미지가 존재하지 않습니다: {image_path}")
            
        # 1. API 검출 시도
        try:
            logger.info("PlanParser API 추론 시도: url=%s", self.api_url)
            return self.detect_api(image_path)
        except Exception as e:
            logger.debug("PlanParser API 연동 실패: %s", e)
            
        # 2. 로컬 검출 시도
        try:
            logger.info("PlanParser 로컬 추론 시도...")
            return self.detect_local(image_path)
        except Exception as e:
            logger.debug("PlanParser 로컬 추론 실패: %s", e)
            
        # 3. Graceful Fallback
        logger.warning("PlanParser 어댑터를 사용할 수 없어 Mock Fallback으로 전환합니다.")
        return self._dummy_detect(image_path)

    def detect_api(self, image_path: Path) -> DetectionOutput:
        """FastAPI 백엔드 서버에 이미지를 전송하여 심볼 리스트를 가져옵니다."""
        with open(image_path, "rb") as f:
            files = {"file": (image_path.name, f, "image/png")}
            resp = requests.post(self.api_url, files=files, timeout=30.0)
            
        if resp.status_code != 200:
            raise RuntimeError(f"PlanParser API 요청 실패 (상태코드: {resp.status_code}): {resp.text}")
            
        raw_data = resp.json()
        # 기대 데이터 형식: {"symbols": [{"class": "door", "bbox": [x1,y1,x2,y2], "confidence": 0.9}, ...]}
        # 또는 리스트 형태의 원시 응답
        symbols_list = []
        if isinstance(raw_data, dict):
            raw_symbols = raw_data.get("symbols", raw_data.get("predictions", []))
        else:
            raw_symbols = raw_data
            
        for s in raw_symbols:
            symbols_list.append(SymbolDetection.from_planparser_dict(s))
            
        logger.info("PlanParser API 추론 완료: 검출 개수=%d", len(symbols_list))
        return DetectionOutput(symbols=symbols_list)

    def detect_local(self, image_path: Path) -> DetectionOutput:
        """로컬 시스템 상에서 ultralytics 라이브러리와 가중치(.pt)를 사용해 추론을 구동합니다."""
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise ImportError("로컬 추론을 위해선 'pip install ultralytics'가 필요합니다.") from exc
            
        # 모델 찾기
        weights = list(self.planparser_dir.glob("**/*best.pt")) + list(self.planparser_dir.glob("**/*.pt"))
        if not weights:
            raise FileNotFoundError("planparser 디렉토리 내에서 YOLO 가중치(.pt) 파일을 찾을 수 없습니다.")
            
        model_path = weights[0]
        logger.info("로컬 YOLO 모델 로드: %s", model_path.name)
        model = YOLO(str(model_path))
        
        results = model.predict(source=str(image_path), conf=0.25, verbose=False)
        symbols_list = []
        
        if results:
            res = results[0]
            names = res.names
            boxes = res.boxes
            for box in boxes:
                cls_id = int(box.cls[0].item())
                class_name = names[cls_id]
                conf = float(box.conf[0].item())
                # bbox: [x1, y1, x2, y2]
                xyxy = box.xyxy[0].tolist()
                
                # Pydantic 딕셔너리로 어댑터 매핑
                det_dict = {
                    "class": class_name,
                    "confidence": conf,
                    "bbox": xyxy
                }
                symbols_list.append(SymbolDetection.from_planparser_dict(det_dict))
                
        logger.info("PlanParser 로컬 추론 완료: 검출 개수=%d", len(symbols_list))
        return DetectionOutput(symbols=symbols_list)

    def _dummy_detect(self, image_path: Path) -> DetectionOutput:
        """Raster2Seq Mock 결과의 기하 좌표 배치에 정확히 맞춰 모의 심볼 검출 결과를 반환합니다.

        이를 통해 스케일 계산(scale_calibration), 문/창문 개구부 매핑(openings), 
        레이어 분기 및 DXF 최종 산출물의 무결성을 실감나게 검증할 수 있습니다.
        """
        logger.info("Mock PlanParser 결과를 생성합니다. (대상: %s)", image_path.name)
        
        # 이미지 크기 추정
        width, height = 1200, 800
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                width, height = img.size
        except Exception:
            pass
            
        x1, y1 = 50.0, 50.0
        x2, y2 = float(width - 50), float(height - 50)
        mx = (x1 + x2) / 2.0
        my = (y1 + y2) / 2.0
        bx_mid = (x1 + mx) / 2.0
        
        symbols = []
        
        # 1. 문 (Doors)
        # 현관문 (Living Room 우측벽 하단 부근)
        symbols.append(SymbolDetection(
            type="door",
            bbox=[x2 - 10, y2 - 160, x2 + 10, y2 - 40],
            confidence=0.91,
            source="planparser_mock",
            class_name="door"
        ))
        
        # Bedroom 문 (Bedroom 하단벽 중앙 부근)
        symbols.append(SymbolDetection(
            type="door",
            bbox=[bx_mid - 45, my - 10, bx_mid + 45, my + 10],
            confidence=0.89,
            source="planparser_mock",
            class_name="door"
        ))
        
        # 2. 창문 (Windows)
        # Living Room 창문 (우측벽 상단 부근)
        symbols.append(SymbolDetection(
            type="window",
            bbox=[x2 - 10, y1 + 90, x2 + 10, y2 - 240],
            confidence=0.90,
            source="planparser_mock",
            class_name="window"
        ))
        
        # Bedroom 창문 (상단벽 중앙 부근)
        symbols.append(SymbolDetection(
            type="window",
            bbox=[bx_mid - 85, y1 - 10, bx_mid + 85, y1 + 10],
            confidence=0.92,
            source="planparser_mock",
            class_name="window"
        ))
        
        # 3. 텍스트 및 치수선 감지 (Scale Calibration 검증용)
        # 도면 상단에 치수 텍스트 "3600"과 하단에 치수 텍스트 "2400" 배치
        # 가로 벽체(상단)의 실제 픽셀 길이는 mx - x1 = 550px.
        # scale_factor = 3600 / 550 = 6.54 mm/px
        
        # 상단 "3600" 치수 문자 bbox (상단 외곽벽 중앙 근처에 배치)
        symbols.append(SymbolDetection(
            type="text",
            bbox=[bx_mid - 40, y1 - 35, bx_mid + 40, y1 - 5],
            confidence=0.98,
            source="planparser_mock",
            class_name="text"
        ))
        # 텍스트 내용 주입 (OCR 대용)
        symbols[-1].id = "TXT-3600"  # ID를 통해 문자 식별
        
        # 4. 기둥 (Column) - 모서리 네 군데 배치
        symbols.append(SymbolDetection(
            type="column",
            bbox=[x1 - 15, y1 - 15, x1 + 15, y1 + 15],
            confidence=0.86,
            source="planparser_mock",
            class_name="column"
        ))
        symbols.append(SymbolDetection(
            type="column",
            bbox=[x2 - 15, y1 - 15, x2 + 15, y1 + 15],
            confidence=0.88,
            source="planparser_mock",
            class_name="column"
        ))
        symbols.append(SymbolDetection(
            type="column",
            bbox=[x1 - 15, y2 - 15, x1 + 15, y2 + 15],
            confidence=0.85,
            source="planparser_mock",
            class_name="column"
        ))
        
        # 5. 가구 (Furniture) - 방 내부 배치
        # Bedroom 내 침대 박스
        symbols.append(SymbolDetection(
            type="furniture",
            bbox=[x1 + 40, y1 + 40, x1 + 200, y1 + 220],
            confidence=0.78,
            source="planparser_mock",
            class_name="bed"
        ))
        
        return DetectionOutput(symbols=symbols)
