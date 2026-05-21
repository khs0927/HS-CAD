import json
from pathlib import Path

from .schema import QAMarkup, QAMarkupItem


def _load_json(path: str | Path | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_qa_markup(styled_result_path: str | Path | None, preview_session_path: str | Path | None = None) -> QAMarkup:
    styled = _load_json(styled_result_path)
    session = _load_json(preview_session_path)
    markup = QAMarkup(metadata={"preview_session": session.get("session_id")})

    if not styled:
        markup.warnings.append("styled_result missing or invalid")
        return markup

    for item in styled.get("entities", []):
        original = item.get("original_entity") or {}
        if item.get("needs_review") or original.get("confidence", 1.0) < 0.65:
            geom = original.get("geometry") or {}
            bbox = geom.get("bbox")
            markup.items.append(
                QAMarkupItem(
                    id=str(original.get("id") or "entity"),
                    type=f"review_{original.get('entity_type', 'unknown')}",
                    severity="medium",
                    bbox=bbox,
                    message=f"검수 필요: {original.get('entity_type', 'unknown')} 신뢰도 또는 스타일 매핑 확인",
                    recommended_action="CAD에서 위치, 레이어, 두께, 문/창 연결 상태를 확인하세요.",
                )
            )
    return markup
