import json
from pathlib import Path

from .schema import QAMarkup, to_dict


def write_qa_json(markup: QAMarkup, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(to_dict(markup), ensure_ascii=False, indent=2), encoding="utf-8")


def write_qa_md(markup: QAMarkup, path: str | Path) -> None:
    lines = [
        "# QA Visual Review",
        "",
        f"- Item count: {len(markup.items)}",
        "",
        "## Items",
    ]
    for item in markup.items:
        lines.append(f"- {item.id}: {item.type}, severity={item.severity}, bbox={item.bbox}, message={item.message}")
    lines += ["", "## Warnings"]
    for warning in markup.warnings or ["none"]:
        lines.append(f"- {warning}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
