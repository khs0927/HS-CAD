from __future__ import annotations

import json

from pydantic import ValidationError

from neuro_seq_cad.vlm.schemas import VLMRefinementResult


def parse_vlm_json_with_retry(payloads: list[str], max_retries: int = 2) -> tuple[VLMRefinementResult, list[str]]:
    warnings: list[str] = []
    for payload in payloads[: max_retries + 1]:
        try:
            return VLMRefinementResult.model_validate(json.loads(payload)), warnings
        except (json.JSONDecodeError, ValidationError) as exc:
            warnings.append(f"vlm_validation_failed: {exc}")
    return VLMRefinementResult(), warnings

