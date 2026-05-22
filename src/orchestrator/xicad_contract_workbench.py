from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json

from .xicad_contracts import default_contract_for_alias


@dataclass(frozen=True)
class ContractSessionTemplate:
    alias: str
    function: str
    category: str
    objective: str
    manual_steps: list[str]
    required_evidence_fields: list[str]
    safety_checks: list[str]
    output_record_hint: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_contract_session_template(alias: str) -> ContractSessionTemplate:
    contract = default_contract_for_alias(alias)
    alias = contract.alias
    return ContractSessionTemplate(
        alias=alias,
        function=contract.function,
        category=contract.category,
        objective=f"Manually verify the argument contract for {alias} / {contract.function}.",
        manual_steps=[
            "Open a disposable test DWG in ZWCAD.",
            "Confirm the drawing has no important unsaved work.",
            f"Run XiCAD alias `{alias}` manually in the command line.",
            "Record each prompt shown by ZWCAD/XiCAD in order.",
            "Enter minimal safe test arguments on a disposable drawing.",
            "Observe whether an entity is created and on which layer.",
            "Run UNDO and confirm the drawing returns to the previous state.",
            "Confirm no Save, Delete, Explode, Purge, or plot action happened.",
            "Use xicad-contract-record to write the observation JSON.",
        ],
        required_evidence_fields=[
            "status",
            "manual_zwcad_version",
            "xicad_version or xicad_root",
            "observed_prompt_sequence",
            "accepted_argument_pattern",
            "output_observation",
            "rollback_observation",
            "safety_observation",
            "no_save_confirmed",
            "no_delete_confirmed",
            "no_explode_confirmed",
        ],
        safety_checks=[
            "Use a disposable test DWG.",
            "Do not test on production drawings.",
            "Do not accept commands that request delete/explode/save/purge.",
            "Record any unexpected side effect as failed.",
            "Keep recipe_registry unchanged until human review.",
        ],
        output_record_hint={
            "alias": alias,
            "status": "passed or failed",
            "manual_zwcad_version": "",
            "xicad_root": "C:/XICAD",
            "observed_prompt_sequence": [],
            "accepted_argument_pattern": [],
            "output_observation": "",
            "rollback_observation": "",
            "safety_observation": "",
            "no_save_confirmed": False,
            "no_delete_confirmed": False,
            "no_explode_confirmed": False,
        },
    )


def render_session_markdown(template: ContractSessionTemplate) -> str:
    lines = [
        f"# XiCAD Contract Session: {template.alias}",
        "",
        f"- Function: {template.function}",
        f"- Category: {template.category}",
        f"- Objective: {template.objective}",
        "",
        "## Manual Steps",
    ]
    lines += [f"{i+1}. {step}" for i, step in enumerate(template.manual_steps)]
    lines += ["", "## Required Evidence Fields"]
    lines += [f"- {field}" for field in template.required_evidence_fields]
    lines += ["", "## Safety Checks"]
    lines += [f"- {check}" for check in template.safety_checks]
    lines += ["", "## Record Hint", "```json", json.dumps(template.output_record_hint, ensure_ascii=False, indent=2), "```"]
    return "\n".join(lines) + "\n"


def write_contract_session(alias: str, out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    template = build_contract_session_template(alias)
    json_path = out / f"{template.alias}_contract_session.json"
    md_path = out / f"{template.alias}_contract_session.md"
    json_path.write_text(json.dumps(template.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_session_markdown(template), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def write_review_matrix(aliases: str | list[str], out_dir: str | Path) -> dict[str, str]:
    if isinstance(aliases, str):
        alias_list = [item.strip().upper() for item in aliases.split(",") if item.strip()]
    else:
        alias_list = [str(item).strip().upper() for item in aliases if str(item).strip()]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = [build_contract_session_template(alias).to_dict() for alias in alias_list]
    json_path = out / "xicad_contract_review_matrix.json"
    md_path = out / "xicad_contract_review_matrix.md"
    json_path.write_text(json.dumps({"aliases": alias_list, "sessions": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# XiCAD Contract Review Matrix",
        "",
        "| Alias | Function | Category | Required Evidence Count |",
        "|---|---|---|---:|",
    ]
    for row in rows:
        lines.append(f"| {row['alias']} | {row['function']} | {row['category']} | {len(row['required_evidence_fields'])} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}
