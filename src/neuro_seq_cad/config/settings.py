"""
settings.py — 전역 파이프라인 설정 (Pydantic v2 BaseSettings)

모든 설정값은 환경변수 또는 .env 파일에서 로드됩니다.
접두사: NEUROCAD_  (예: NEUROCAD_SNAP_THRESHOLD=5.0)
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 프로젝트 루트 디렉토리 자동 탐색
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent          # config/
_SRC_DIR = _THIS_DIR.parent                          # neuro_seq_cad/
_PROJECT_ROOT = _SRC_DIR.parent.parent               # unified_floorplan_to_cad/


class NeuroCADSettings(BaseSettings):
    """NeuroSeqCAD 파이프라인 전역 설정.

    값 우선순위: 환경변수 > .env 파일 > 기본값
    환경변수 접두사는 ``NEUROCAD_`` 입니다.
    """

    model_config = SettingsConfigDict(
        env_prefix="NEUROCAD_",
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # 외부 모델 디렉토리 (External model/repo directories)
    # ------------------------------------------------------------------
    raster2seq_dir: Path = Field(
        default=_PROJECT_ROOT / "externals" / "Raster2Seq",
        description="Raster2Seq 저장소 경로 (체크포인트 포함)",
    )
    planparser_dir: Path = Field(
        default=_PROJECT_ROOT / "externals" / "planparser",
        description="PlanParser 저장소 경로 (YOLO/Faster-RCNN 모델)",
    )
    mlsd_dir: Path = Field(
        default=_PROJECT_ROOT / "externals" / "mlsd",
        description="MLSD 라인 검출기 저장소 경로 (TFLite 모델)",
    )

    # ------------------------------------------------------------------
    # VLM (Vision-Language Model) 설정
    # ------------------------------------------------------------------
    vlm_api_key: Optional[str] = Field(
        default=None,
        description="VLM API 키 (GPT-4o / Claude Vision 등)",
    )
    vlm_model: str = Field(
        default="gpt-4o",
        description="사용할 VLM 모델 이름",
    )
    vlm_base_url: Optional[str] = Field(
        default=None,
        description="VLM API base URL (사설 엔드포인트용)",
    )

    # ------------------------------------------------------------------
    # 기하 후처리 임계값 (Geometry post-processing thresholds)
    # ------------------------------------------------------------------
    snap_threshold: float = Field(
        default=5.0,
        ge=0.0,
        description="스냅 임계값 (px) — 이 거리 이내의 끝점은 하나로 병합",
    )
    ortho_threshold: float = Field(
        default=7.5,
        ge=0.0,
        le=45.0,
        description="직교화 임계값 (°) — 수평/수직과의 각도 차이가 이 값 이하이면 보정",
    )
    confidence_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="객체 검출 신뢰도 최소값 — 이 값 미만은 폐기",
    )

    # ------------------------------------------------------------------
    # 스케일 및 좌표계 (Scale & coordinate system)
    # ------------------------------------------------------------------
    default_scale: float = Field(
        default=1.0,
        gt=0.0,
        description="이미지 → CAD 기본 스케일 팩터 (pixels → mm)",
    )

    # ------------------------------------------------------------------
    # DXF 출력 설정 (DXF output settings)
    # ------------------------------------------------------------------
    dxf_version: Literal["R12", "R2000", "R2004", "R2007", "R2010", "R2013", "R2018"] = Field(
        default="R2010",
        description="ezdxf DXF 파일 버전",
    )
    output_dir: Path = Field(
        default=_PROJECT_ROOT / "output",
        description="DXF / 디버그 이미지 저장 디렉토리",
    )
    debug_dir: Path = Field(
        default=_PROJECT_ROOT / "output" / "debug",
        description="전처리 중간 결과 저장 디렉토리",
    )

    # ------------------------------------------------------------------
    # 디바이스 설정 (Device settings)
    # ------------------------------------------------------------------
    device: str = Field(
        default="cuda",
        description="PyTorch 디바이스 (cuda / cpu / mps)",
    )

    # ------------------------------------------------------------------
    # PlanParser FastAPI 서버 설정
    # ------------------------------------------------------------------
    planparser_host: str = Field(default="127.0.0.1", description="PlanParser 서버 호스트")
    planparser_port: int = Field(default=8000, ge=1, le=65535, description="PlanParser 서버 포트")

    # ------------------------------------------------------------------
    # 로깅 레벨
    # ------------------------------------------------------------------
    log_level: str = Field(default="INFO", description="로그 레벨 (DEBUG/INFO/WARNING/ERROR)")

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("device")
    @classmethod
    def _normalize_device(cls, v: str) -> str:
        """디바이스 문자열 정규화 (소문자 변환 및 기본 검증)."""
        v = v.strip().lower()
        valid_prefixes = ("cpu", "cuda", "mps")
        if not any(v.startswith(p) for p in valid_prefixes):
            logger.warning("알 수 없는 디바이스 '%s', cpu로 대체합니다.", v)
            return "cpu"
        return v

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, v: str) -> str:
        """로그 레벨 문자열 정규화 (대문자 변환)."""
        return v.strip().upper()

    # ------------------------------------------------------------------
    # Helper properties
    # ------------------------------------------------------------------
    @property
    def planparser_url(self) -> str:
        """PlanParser /predict 엔드포인트 전체 URL."""
        return f"http://{self.planparser_host}:{self.planparser_port}/predict"

    @property
    def raster2seq_checkpoint(self) -> Path:
        """Raster2Seq CubiCasa 체크포인트 기본 경로."""
        return self.raster2seq_dir / "checkpoints" / "cubicasa.ckpt"

    @property
    def mlsd_tflite_model(self) -> Path:
        """MLSD TFLite 모델 기본 경로."""
        return self.mlsd_dir / "tflite_models" / "M-LSD_512_large_fp32.tflite"

    def ensure_dirs(self) -> None:
        """출력/디버그 디렉토리가 없으면 생성."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.debug_dir.mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:
        safe_fields = self.model_dump()
        # VLM API 키는 마스킹
        if safe_fields.get("vlm_api_key"):
            key = safe_fields["vlm_api_key"]
            safe_fields["vlm_api_key"] = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "****"
        return f"NeuroCADSettings({safe_fields})"


# ---------------------------------------------------------------------------
# 싱글턴 캐시 — 모듈 전역에서 get_settings()로 접근
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_settings() -> NeuroCADSettings:
    """NeuroCADSettings 싱글턴 인스턴스를 반환합니다.

    최초 호출 시 .env 파일과 환경변수에서 설정을 로드하며,
    이후 호출에서는 캐시된 인스턴스를 반환합니다.
    """
    settings = NeuroCADSettings()
    settings.ensure_dirs()
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    logger.info("NeuroCAD 설정 로드 완료 — DXF %s, device=%s", settings.dxf_version, settings.device)
    return settings
