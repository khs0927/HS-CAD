"""Intent parser for natural language CAD commands.

The parser is rule‑based and operates on lower‑cased command strings.
It extracts a high‑level *intent_type* and simple *parameters* that are
required by the orchestrator planner. The implementation deliberately
avoids any external LLM calls – the logic is fully deterministic so that
unit tests are reliable.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from .task_schema import TaskIntent

# ---------------------------------------------------------------------------
# Keyword mapping – each key is a lowercase intent label and the value is a
# list of substrings that, when present in the user command, indicate that
# intent. The order matters: earlier entries take precedence.
# ---------------------------------------------------------------------------
_INTENT_KEYWORDS: dict[str, List[str]] = {
    "analyze_active_drawing": ["분석", "현재 도면", "레이어 문제", "도면 상태", "객체 수", "레이어 수"],
    "analyze_zero_layer": ["0번 레이어", "레이어 0", "layer 0"],
    "dynamic_block_report": ["동적 블록", "effectivename", "블록 수량", "문 블록", "창호 블록"],
    "remap_layers_preview": ["정리", "remap", "레이어 이동", "wal1로", "txt로", "hat로", "미리보기"],
    "xicad_safe_plan": ["xicad", "safe plan", "명령 계획", "wal 실행 계획", "실행하지 말고"],
    "xicad_execute_preview": ["xicad 실행", "명령 실행", "실행하지만"],
    "lisp_preview_load": ["lisp 로드 검증", "리습 경로", "로드 가능한지", "실행하지 말고"],
    "lisp_live_load": ["lisp 로드 실행", "로드 실행"],
    "insert_image_result": ["output_corrected.dxf", "이미지 도면", "삽입", "블록으로", "base point", "scale", "rotation"],
    "undo_preview": ["되돌려", "undo", "undo back", "뒤로가기"],
}

# ---------------------------------------------------------------------------
# Helper regex patterns for simple parameter extraction
# ---------------------------------------------------------------------------
_PATH_RE = re.compile(r"(?P<path>\S+\.(?:dwg|dxf))", re.IGNORECASE)
_LAYER_RE = re.compile(r"(?P<layer>[A-Za-z0-9@_\-]+)\s*->\s*(?P<target>[A-Za-z0-9@_\-]+)", re.IGNORECASE)
_ALIAS_RE = re.compile(r"\b([A-Z]{2,})\b")  # simple uppercase token for XiCAD alias


def detect_intent_type(command: str) -> str:
    """Return the intent label that best matches *command*.

    The function lower‑cases the input and checks the keyword lists in the
    order they appear in ``_INTENT_KEYWORDS``. If no match is found, the
    intent ``unknown`` is returned.
    """
    lowered = command.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(kw.lower() in lowered for kw in keywords):
            return intent
    return "unknown"


def extract_parameters(command: str) -> Dict[str, Any]:
    """Extract a small set of parameters used by the planner.

    The extraction is intentionally lightweight – only the values needed by the
    unit tests are captured.
    """
    params: Dict[str, Any] = {}
    # file path
    m = _PATH_RE.search(command)
    if m:
        params["file_path"] = m.group("path")
    # layer remap pairs
    layer_mappings = []
    for m in _LAYER_RE.finditer(command):
        layer_mappings.append({"source": m.group("layer"), "target": m.group("target")})
    if layer_mappings:
        params["layer_mappings"] = layer_mappings
    # XiCAD alias – first uppercase token of length >=2
    m = _ALIAS_RE.search(command)
    if m:
        params["xicad_alias"] = m.group(1)
    # numeric values for scale/rotation/base‑point (simple heuristic)
    numbers = re.findall(r"[-+]?[0-9]*\.?[0-9]+", command)
    if numbers:
        # treat first three numbers as a point if present
        if len(numbers) >= 2:
            params["base_point"] = [float(numbers[0]), float(numbers[1])]
        if len(numbers) >= 3:
            try:
                params["scale"] = float(numbers[2])
            except Exception:
                pass
        if len(numbers) >= 4:
            try:
                params["rotation"] = float(numbers[3])
            except Exception:
                pass
    return params


def detect_risk_level(intent: TaskIntent) -> str:
    """Very coarse risk estimation based on intent type.

    • ``xicad_execute_preview`` and ``lisp_live_load`` are treated as
      ``high`` because they could modify the drawing.
    • All other intents are ``low``.
    """
    high_risk_intents = {"xicad_execute_preview", "lisp_live_load"}
    return "high" if intent.intent_type in high_risk_intents else "low"


def detect_required_systems(intent: TaskIntent) -> TaskIntent:
    """Populate the ``requires_*`` flags based on ``intent_type``.
    """
    zwcad_intents = {
        "analyze_active_drawing",
        "analyze_zero_layer",
        "dynamic_block_report",
        "remap_layers_preview",
        "lisp_preview_load",
        "lisp_live_load",
        "insert_image_result",
        "undo_preview",
    }
    xicad_intents = {"xicad_safe_plan", "xicad_execute_preview"}
    lisp_intents = {"lisp_preview_load", "lisp_live_load"}
    image_intents = {"insert_image_result"}

    intent.requires_zwcad = intent.intent_type in zwcad_intents
    intent.requires_xicad = intent.intent_type in xicad_intents
    intent.requires_lisp = intent.intent_type in lisp_intents
    intent.requires_image_result = intent.intent_type in image_intents
    return intent


def parse_user_command(command: str) -> TaskIntent:
    """Parse *command* into a :class:`TaskIntent` model.

    The function performs three steps:
    1. Detect the high‑level intent type.
    2. Extract any simple parameters.
    3. Populate risk and system requirement flags.
    """
    intent_type = detect_intent_type(command)
    params = extract_parameters(command)
    # Use a generic action derived from intent_type for now
    action = intent_type.replace("_", " ")
    intent = TaskIntent(
        raw_user_command=command,
        intent_type=intent_type,
        action=action,
        parameters=params,
    )
    intent.risk_level = detect_risk_level(intent)
    intent = detect_required_systems(intent)
    # Provide a short reason for the chosen intent – useful for debugging
    intent.reason = f"Detected intent {intent_type} via keyword matching"
    return intent
