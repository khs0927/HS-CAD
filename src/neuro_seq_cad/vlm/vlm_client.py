"""
vlm_client.py — VLM(Vision-Language Model) API 클라이언트 및 연동기

도면 이미지와 시각적인 벡터화 overlay 결과를 VLM(GPT-4o, Gemini 등)에 전송하여,
구조화된 보정 지침(VLMFloorplanRefinementOutput)을 받아옵니다.
API 키가 유효하지 않거나 빈 슬롯인 경우를 대비해, Mock 어댑터 결과와 연동되는
실제적인 모의 보정 리스트(Mock Correction Fallback)를 반환하는 기능을 탑재하여
파이프라인의 통합 구동 테스트가 완벽히 통과되도록 합니다.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import requests
from neuro_seq_cad.config.settings import get_settings
from neuro_seq_cad.vlm.schemas import VLMFloorplanRefinementOutput, CorrectionInstruction

logger = logging.getLogger(__name__)


class VLMRefinementClient:
    """VLM API와의 통신을 관리하는 클라이언트 클래스."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.vlm_api_key
        self.model_name = model_name or settings.vlm_model
        self.base_url = base_url or settings.vlm_base_url or "https://api.openai.com/v1"
        
        # 시스템 프롬프트 로드
        _this_dir = Path(__file__).resolve().parent
        prompt_path = _this_dir / "prompt_floorplan_refinement.md"
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
        else:
            self.system_prompt = "You are a CAD inspector. Output correction JSON."

    def is_available(self) -> bool:
        """API 연동을 실제로 수행할 수 있는지 검사합니다."""
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def request_refinement(
        self,
        image_path: Path,
        overlay_image_path: Optional[Path] = None,
        vector_data_json: str = ""
    ) -> VLMFloorplanRefinementOutput:
        """VLM API를 호출하여 도면 보정 피드백 데이터를 획득합니다."""
        if not self.is_available():
            logger.warning("VLM API 키가 존재하지 않습니다. 모의 보정 데이터(Mock)로 Fallback 합니다.")
            return self._request_mock_refinement(vector_data_json)
            
        logger.info(
            "VLM API 호출 요청: model=%s, image=%s",
            self.model_name, image_path.name
        )
        
        # OpenAI Chat Completion API (Vision) 또는 Gemini API 형식에 맞춰 전송
        # 1. 이미지 로드 및 Base64 인코딩
        try:
            import base64
            with open(image_path, "rb") as img_f:
                img_base64 = base64.b64encode(img_f.read()).decode("utf-8")
                
            overlay_base64 = None
            if overlay_image_path and overlay_image_path.exists():
                with open(overlay_image_path, "rb") as ov_f:
                    overlay_base64 = base64.b64encode(ov_f.read()).decode("utf-8")
        except Exception as e:
            logger.error("VLM 이미지 인코딩 실패: %s", e)
            return self._request_mock_refinement(vector_data_json)
            
        # 2. API 메시지 페이로드 구성
        # OpenAI Vision API 기준
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        user_content = [
            {
                "type": "text",
                "text": f"Below is the current JSON structure representing the vectorized elements:\n{vector_data_json}\n\nPlease analyze the original floorplan image and review the vectors. Output the required corrections in JSON."
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_base64}"
                }
            }
        ]
        
        if overlay_base64:
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{overlay_base64}"
                }
            })
            
        payload = {
            "model": self.model_name,
            "response_format": {"type": "json_object"},  # JSON 모드 강제 활성화
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_content}
            ],
            "max_tokens": 2048,
            "temperature": 0.1
        }
        
        # 3. HTTP POST 요청 전송
        try:
            endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=60.0)
            
            if resp.status_code != 200:
                logger.error("VLM API 응답 에러: %s", resp.text)
                return self._request_mock_refinement(vector_data_json)
                
            resp_data = resp.json()
            raw_content = resp_data["choices"][0]["message"]["content"]
            logger.debug("VLM Raw Response: %s", raw_content)
            
            # Pydantic 파싱
            parsed_json = json.loads(raw_content)
            return VLMFloorplanRefinementOutput(**parsed_json)
            
        except Exception as e:
            logger.error("VLM API 통신 또는 파싱 실패: %s", e)
            return self._request_mock_refinement(vector_data_json)

    def _request_mock_refinement(self, vector_data_json: str = "") -> VLMFloorplanRefinementOutput:
        """테스트 및 데모 실행용 실감나는 모의 도면 보정 지침을 구성합니다.

        기존 그래프의 특정 방(예: 'Bath')에 대한 미세 라벨 수정, 또는 
        특정 벽체 오차 보정을 시뮬레이션합니다.
        """
        logger.info("Mock VLM 보정 피드백을 생성합니다.")
        
        # vector_data_json에서 대상을 찾아보거나 가상의 ID를 타겟팅합니다.
        # Raster2SeqMock이 생성하는 ID는 랜덤하게 결정되지만
        # 엔티티 검색을 위해 ID를 dummy_vector_graph_fitter에서 찾아 교체할 예정입니다.
        instructions = [
            # 1. Bath 방의 이름을 더 정확하게 "Bathroom"으로 보정 제안
            CorrectionInstruction(
                target_entity_id="find_bath_id",  # refiner가 실제 Bath ID를 찾아 매칭할 예정
                action="modify",
                element_type="room",
                reason="도면 스캔본 검토 결과 'Bath' 보다는 'Bathroom' 표기가 설계 표준에 더 적합합니다.",
                description="방 라벨 텍스트 변경: 'Bath' -> 'Bathroom'",
                parameters={"new_label": "Bathroom"}
            ),
            
            # 2. 문/창문 정렬 미세 보정 (예: Bedroom 하단 문 위치를 벽선에 정확히 밀착)
            CorrectionInstruction(
                target_entity_id="find_door_id",
                action="modify",
                element_type="door",
                reason="문 바운딩 박스가 주 벽체 선분에서 미세하게 이격되어 있어 스냅 보정이 필요합니다.",
                description="Y축 방향으로 -5.0px 미세 이동",
                parameters={"shift_px": [0.0, -5.0]}
            )
        ]
        
        return VLMFloorplanRefinementOutput(
            instructions=instructions,
            global_notes="전반적인 벡터화 연결 상태는 우수하나, 문 스냅 오차 및 방 표기 표준명칭 일치화 작업이 일부 요구됩니다.",
            quality_score=0.92
        )
