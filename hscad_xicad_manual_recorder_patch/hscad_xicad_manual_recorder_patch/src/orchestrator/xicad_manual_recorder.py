from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json

from .xicad_contracts import XiCADContractEvidence, default_contract_for_alias, write_evidence
from .xicad_contract_validator import validate_contract_evidence, write_validation_result


@dataclass(frozen=True)
class ManualRecordTemplate:
    alias: str
    function: str
    category: str
    instructions: list[str]
    template: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_manual_record_template(alias: str) -> ManualRecordTemplate:
    contract = default_contract_for_alias(alias)
    alias = contract.alias
    return ManualRecordTemplate(
        alias=alias,
        function=contract.function,
        category=contract.category,
        instructions=[
            "Run the XiCAD alias manually in a disposable ZWCAD test drawing.",
            "Record the exact prompt sequence shown in the command line.",
            "Record the accepted argument pattern, not just the values.",
            "Confirm undo restores the previous drawing state.",
            "Confirm no save/delete/explode side effects occurred.",
        ],
        template={
            "alias": alias,
            "status": "passed or failed",
            "manual_zwcad_version": "",
            "xicad_version": "",
            "xicad_root": "C:/XICAD",
            "observed_prompt_sequence": [],
            "accepted_argument_pattern": [],
            "output_observation": "",
            "rollback_observation": "",
            "safety_observation": "",
            "no_save_confirmed": False,
            "no_delete_confirmed": False,
            "no_explode_confirmed": False,
            "notes": "",
        },
    )


def write_manual_record_template(alias: str, out: str | Path) -> str:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    template = build_manual_record_template(alias)
    path.write_text(json.dumps(template.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def evidence_from_manual_answers(alias: str, answers: dict[str, Any]) -> XiCADContractEvidence:
    def seq(name: str) -> tuple[str, ...]:
        value = answers.get(name, ())
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split("|") if part.strip())
        if isinstance(value, list | tuple):
            return tuple(str(part).strip() for part in value if str(part).strip())
        return ()

    return XiCADContractEvidence(
        alias=alias.upper(),
        status=str(answers.get("status", "failed")),
        manual_zwcad_version=str(answers.get("manual_zwcad_version", "")),
        xicad_version=str(answers.get("xicad_version", "")),
        xicad_root=str(answers.get("xicad_root", "")),
        observed_prompt_sequence=seq("observed_prompt_sequence"),
        accepted_argument_pattern=seq("accepted_argument_pattern"),
        output_observation=str(answers.get("output_observation", "")),
        rollback_observation=str(answers.get("rollback_observation", "")),
        safety_observation=str(answers.get("safety_observation", "")),
        no_save_confirmed=bool(answers.get("no_save_confirmed", False)),
        no_delete_confirmed=bool(answers.get("no_delete_confirmed", False)),
        no_explode_confirmed=bool(answers.get("no_explode_confirmed", False)),
        notes=str(answers.get("notes", "")),
    )


def write_manual_evidence_and_validation(alias: str, answers: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    evidence = evidence_from_manual_answers(alias, answers)
    record_path = out / f"{evidence.alias}_record.json"
    validation_path = out / f"{evidence.alias}_validation.json"
    write_evidence(evidence, record_path)
    result = validate_contract_evidence(evidence, evidence_path=record_path)
    write_validation_result(result, validation_path)
    return {"record": str(record_path), "validation": str(validation_path)}


def build_record_command_example(alias: str) -> str:
    alias = alias.upper()
    return (
        f'python -m src.main xicad-contract-record --alias {alias} --status passed '
        '--zwcad-version "ZWCAD 2026" --xicad-root "C:/XICAD" '
        '--prompts "prompt1|prompt2|prompt3" '
        '--args-pattern "point|point|number" '
        '--output-observation "describe created entity/layer/result" '
        '--rollback-observation "undo restored previous state" '
        '--safety-observation "no save/delete/explode observed" '
        '--no-save-confirmed --no-delete-confirmed --no-explode-confirmed '
        f'--out outputs/xicad_contracts/{alias}_record.json'
    )
