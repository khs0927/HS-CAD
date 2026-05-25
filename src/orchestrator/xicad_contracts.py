from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any
import json


class ContractStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    MANUAL_TEST_PENDING = "MANUAL_TEST_PENDING"
    MANUAL_VERIFIED = "MANUAL_VERIFIED"
    SCRIPTABLE_CANDIDATE = "SCRIPTABLE_CANDIDATE"
    BLOCKED = "BLOCKED"


DEFAULT_TARGET_ALIASES = ("WAL", "D1", "W1", "INS", "COL", "BE", "AE", "LC")


@dataclass(frozen=True)
class XiCADArgumentSpec:
    name: str
    arg_type: str
    required: bool = True
    description: str = ""
    example: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class XiCADCommandContract:
    alias: str
    function: str
    category: str
    description: str
    status: ContractStatus = ContractStatus.UNVERIFIED
    argument_specs: tuple[XiCADArgumentSpec, ...] = ()
    expected_prompts: tuple[str, ...] = ()
    script_template: str | None = None
    verified: bool = False
    scriptable: bool = False
    auto_run_allowed: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["argument_specs"] = [spec.to_dict() for spec in self.argument_specs]
        return data


@dataclass(frozen=True)
class XiCADContractEvidence:
    alias: str
    status: str
    manual_zwcad_version: str = ""
    xicad_version: str = ""
    xicad_root: str = ""
    observed_prompt_sequence: tuple[str, ...] = ()
    accepted_argument_pattern: tuple[str, ...] = ()
    output_observation: str = ""
    rollback_observation: str = ""
    safety_observation: str = ""
    no_save_confirmed: bool = False
    no_delete_confirmed: bool = False
    no_explode_confirmed: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "XiCADContractEvidence":
        return cls(
            alias=str(data.get("alias", "")),
            status=str(data.get("status", "")),
            manual_zwcad_version=str(data.get("manual_zwcad_version", "")),
            xicad_version=str(data.get("xicad_version", "")),
            xicad_root=str(data.get("xicad_root", "")),
            observed_prompt_sequence=tuple(data.get("observed_prompt_sequence") or ()),
            accepted_argument_pattern=tuple(data.get("accepted_argument_pattern") or ()),
            output_observation=str(data.get("output_observation", "")),
            rollback_observation=str(data.get("rollback_observation", "")),
            safety_observation=str(data.get("safety_observation", "")),
            no_save_confirmed=bool(data.get("no_save_confirmed", False)),
            no_delete_confirmed=bool(data.get("no_delete_confirmed", False)),
            no_explode_confirmed=bool(data.get("no_explode_confirmed", False)),
            notes=str(data.get("notes", "")),
        )


@dataclass(frozen=True)
class XiCADPromotionCandidate:
    alias: str
    function: str
    verified: bool
    scriptable: bool
    auto_run_allowed: bool
    evidence_path: str
    review_required: bool = True
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_contract_for_alias(alias: str) -> XiCADCommandContract:
    alias = alias.upper()
    meta = {
        "WAL": ("xiDrawWall", "DRAW_ARCH", "벽 그리기"),
        "D1": ("xiDoor1", "DRAW_ARCH", "간단문 그리기"),
        "W1": ("xiWin1", "DRAW_ARCH", "간단창 그리기"),
        "INS": ("xiInsul", "DRAW_ARCH", "단열재 그리기"),
        "COL": ("xiDrawColumn", "DRAW_ARCH", "기둥 그리기"),
        "BE": ("xiBE", "DRAW_STRUCT", "H빔/C채널/L형강 그리기"),
        "AE": ("xiAE", "AREA_QTY", "면적표시 여러요소"),
        "LC": ("xiChangeLayer", "LAYER_MANAGE", "선택객체 켜 변경"),
    }
    function, category, description = meta.get(alias, (alias, "UNKNOWN", "Unregistered XiCAD command"))
    return XiCADCommandContract(
        alias=alias,
        function=function,
        category=category,
        description=description,
        status=ContractStatus.UNVERIFIED,
        verified=False,
        scriptable=False,
        auto_run_allowed=False,
        notes="Default-deny until manual ZWCAD+XiCAD contract evidence is reviewed.",
    )


def build_default_contracts(aliases: tuple[str, ...] | list[str] | None = None) -> list[XiCADCommandContract]:
    return [default_contract_for_alias(alias) for alias in (aliases or DEFAULT_TARGET_ALIASES)]


def write_contract_plan(contracts: list[XiCADCommandContract], out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "xicad_contract_plan.json"
    md_path = out / "xicad_contract_plan.md"
    payload = {
        "mode": "manual_contract_verification",
        "auto_execution": False,
        "contracts": [contract.to_dict() for contract in contracts],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_contract_plan_markdown(contracts), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def render_contract_plan_markdown(contracts: list[XiCADCommandContract]) -> str:
    lines = [
        "# XiCAD Contract Verification Plan",
        "",
        "This plan does not execute XiCAD commands.",
        "",
        "| Alias | Function | Category | Status | Verified | Scriptable | AutoRun |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in contracts:
        lines.append(f"| {c.alias} | {c.function} | {c.category} | {c.status.value} | {c.verified} | {c.scriptable} | {c.auto_run_allowed} |")
    lines += [
        "",
        "## Manual Verification Checklist",
        "- Record ZWCAD version.",
        "- Record XiCAD version or xicad_root.",
        "- Record prompt sequence.",
        "- Record accepted argument pattern.",
        "- Record output observation.",
        "- Record rollback observation.",
        "- Confirm no Save/Delete/Explode occurred.",
    ]
    return "\n".join(lines) + "\n"


def read_evidence(path: str | Path) -> XiCADContractEvidence:
    return XiCADContractEvidence.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def write_evidence(evidence: XiCADContractEvidence, path: str | Path) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out)
