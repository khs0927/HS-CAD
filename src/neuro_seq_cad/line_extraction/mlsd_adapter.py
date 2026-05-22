"""
mlsd_adapter.py — MLSD (Mobile Line Segment Detector) 딥러닝 선분 검출 연동 어댑터

네이버가 공개한 실시간 경량 선분 검출 모델인 M-LSD(TFLite 버전)를 활용하여,
스캔된 도면에서 정밀한 건축 선분을 딥러닝 기반으로 추출합니다.
실행 환경에 tensorflow가 없거나 모델 파일이 누락된 경우,
전통적인 OpenCV LSD/Hough 기법(opencv_lsd)으로 Graceful Fallback을 수행하며
Mock 모드 작동 시 Mock 평면도 구조에 정교하게 매칭되는 모의 선분 세트를 리턴합니다.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import List, Optional

import numpy as np
from neuro_seq_cad.config.settings import get_settings
from neuro_seq_cad.line_extraction.opencv_lsd import LineSegment, LineExtractionOutput, extract_lines_lsd

logger = logging.getLogger(__name__)

# Tensorflow 임포트 시도 (실패 시 로컬 추론은 opencv lsd로 대체)
try:
    import tensorflow as tf
    _TF_AVAILABLE = True
except ImportError:
    tf = None  # type: ignore[assignment]
    _TF_AVAILABLE = False


class MLSDAdapter:
    """M-LSD 선분 검출기 어댑터 클래스."""

    def __init__(
        self,
        mlsd_dir: Optional[Path] = None,
        model_path: Optional[Path] = None
    ) -> None:
        settings = get_settings()
        self.mlsd_dir = mlsd_dir or settings.mlsd_dir
        self.model_path = model_path or settings.mlsd_tflite_model

    def is_available(self) -> bool:
        """Tensorflow 라이브러리와 TFLite 모델 파일이 존재하는지 확인합니다."""
        return _TF_AVAILABLE and self.model_path.exists()

    def extract_lines(self, image: np.ndarray) -> LineExtractionOutput:
        """도면 이미지에서 선분을 추출합니다."""
        if not self.is_available():
            logger.warning("Tensorflow 또는 MLSD TFLite 모델이 없습니다. OpenCV LSD로 폴백합니다.")
            # OpenCV LSD로 대체 처리 (기본 스냅 테스트를 위해 소스 이름 변경)
            output = extract_lines_lsd(image)
            for line in output.lines:
                line.source = "mlsd_fallback"
            return output
            
        return self._extract_tflite(image)

    def _extract_tflite(self, image: np.ndarray) -> LineExtractionOutput:
        """TFLite 모델을 로드하여 선분을 실제로 추출합니다."""
        logger.info("MLSD TFLite 실물 모델 추론 시작: model=%s", self.model_path.name)
        
        try:
            import cv2
        except ImportError:
            raise ImportError("MLSD 이미지 처리를 위해 opencv-python(cv2)이 필요합니다.")
            
        # 1. TFLite 인터프리터 로드
        interpreter = tf.lite.Interpreter(model_path=str(self.model_path))
        interpreter.allocate_tensors()
        
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        # 2. 이미지 전처리
        # 원본 크기 저장
        orig_h, orig_w = image.shape[:2]
        
        # M-LSD는 RGB 512x512 입력을 받습니다.
        if len(image.shape) == 2:
            img_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        else:
            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
        img_resized = cv2.resize(img_rgb, (512, 512))
        
        # [0, 255] -> [-1.0, 1.0] 정규화
        input_data = (img_resized.astype(np.float32) / 127.5) - 1.0
        input_data = np.expand_dims(input_data, axis=0)  # Batch 차원 추가 (1, 512, 512, 3)
        
        # 3. 텐서 설정 및 추론
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        
        # 4. 출력 텐서 분석
        # M-LSD TFLite는 일반적으로 2개 또는 3개의 출력을 가집니다.
        # 출력 1: lines [1, num_lines, 2, 2] (각 선분의 [y1, x1] 및 [y2, x2] 상대좌표)
        # 출력 2: scores [1, num_lines] (신뢰도)
        pts_tensor = interpreter.get_tensor(output_details[0]['index'])[0]      # shape: [num_lines, 2, 2]
        scores_tensor = interpreter.get_tensor(output_details[1]['index'])[0]   # shape: [num_lines]
        
        lines: List[LineSegment] = []
        
        # 상대 좌표를 원본 이미지 픽셀 스케일로 복원하여 LineSegment 모델화
        for i, (pts, score) in enumerate(zip(pts_tensor, scores_tensor)):
            if score < 0.25:  # 신뢰도 임계값 필터
                continue
                
            # pts 형식: [[y1, x1], [y2, x2]]
            y1_rel, x1_rel = pts[0]
            y2_rel, x2_rel = pts[1]
            
            # [0, 1] 비율 좌표를 이미지 크기로 스케일링
            x1 = x1_rel * orig_w
            y1 = y1_rel * orig_h
            x2 = x2_rel * orig_w
            y2 = y2_rel * orig_h
            
            # 각도 및 길이
            dx = x2 - x1
            dy = y2 - y1
            angle = math.degrees(math.atan2(dy, dx))
            length = math.hypot(dx, dy)
            
            lines.append(LineSegment(
                p1=[float(x1), float(y1)],
                p2=[float(x2), float(y2)],
                angle=angle,
                length=length,
                confidence=float(score),
                source="mlsd"
            ))
            
        logger.info("MLSD 추론 완료: 검출 선분 %d개", len(lines))
        return LineExtractionOutput(lines=lines)

    def extract_mock_lines(self, width: int = 1200, height: int = 800) -> LineExtractionOutput:
        """Mock 평면도 벽체 뼈대 구조에 정밀하게 일치하는 검출 선분을 가상으로 만듭니다.

        이 모의 선분들은 geometry snap, merge, 그리고 최종 DXF 변환의 연결 논리를
        실제로 완벽히 구동하도록 돕는 정밀한 기하 좌표 세트입니다.
        """
        logger.info("Mock MLSD 선분 목록을 구성합니다.")
        
        x1, y1 = 50.0, 50.0
        x2, y2 = float(width - 50), float(height - 50)
        mx = (x1 + x2) / 2.0
        my = (y1 + y2) / 2.0
        
        mock_coords = [
            # 1. 외곽 사각형 벽체 라인 (일부러 약간 어긋난 좌표들과 쪼개진 선들로 스냅 기능 테스트 제공)
            [x1 + 1.2, y1, mx, y1], [mx, y1, x2 - 0.8, y1],  # 상단벽 (두 개로 쪼개짐)
            [x2, y1 + 1.5, x2, my], [x2, my, x2, y2 - 0.5],  # 우측벽
            [x2, y2, mx, y2], [mx, y2, x1, y2],              # 하단벽
            [x1, y2 - 1.0, x1, my], [x1, my, x1, y1],        # 좌측벽
            
            # 2. 내부 분할벽
            [mx, y1, mx, my], [mx, my, mx, y2],              # 중앙 수직벽
            [x1, my, mx, my]                                 # 좌측 수평 분할벽
        ]
        
        lines: List[LineSegment] = []
        for i, coord in enumerate(mock_coords):
            lx1, ly1, lx2, ly2 = coord
            dx = lx2 - lx1
            dy = ly2 - ly1
            angle = math.degrees(math.atan2(dy, dx))
            length = math.hypot(dx, dy)
            
            lines.append(LineSegment(
                p1=[lx1, ly1],
                p2=[lx2, ly2],
                angle=angle,
                length=length,
                confidence=0.88 - (i * 0.01),  # 신뢰도 편차 부여
                source="mlsd_mock"
            ))
            
        return LineExtractionOutput(lines=lines)
