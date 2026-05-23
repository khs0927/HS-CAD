"""QA Pipeline module for no-COM ReviewContext DXF bridge.
Implements a simple pipeline that runs fileized or DXF input through the review
engine, generates a command plan, bundles results, and writes a summary.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.integration.reviewcontext_dxf_merge import (
    command_plan_from_review,
    review_dxf_file,
    review_fileized_record,
)


@dataclass
class QAPipelineResult:
    mode: str
    input_path: str
    output_dir: str
    review_report_path: str
    command_plan_report_path: str
    qa_bundle_path: str
    run_summary_path: str
    violation_count: int
    action_candidate_count: int
    command_plan_count: int
    status: str
    warnings: list[str]


class QAPipeline:
    """
    One-shot no-COM QA pipeline.

    This pipeline intentionally does not mutate CAD files.
    It only reads fileized JSON or DXF, produces a review report,
    converts action candidates into dry-run command plans,
    and writes a bundle/summary for human review.
    """

    def __init__(self, output_dir: str | Path = "outputs/qa"):
        self.output_dir = Path(output_dir)

    def run_fileized(
        self,
        input_path: str | Path,
        *,
        engine: str = "zwcad",
    ) -> QAPipelineResult:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        input_path = Path(input_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Fileized input JSON does not exist: {input_path}")

        review_path = self.output_dir / "review_report.json"
        plan_path = self.output_dir / "command_plan_report.json"
        bundle_path = self.output_dir / "QA_BUNDLE.json"
        summary_path = self.output_dir / "RUN_SUMMARY.md"

        warnings: list[str] = []

        review = review_fileized_record(input_path, review_path)
        plan = command_plan_from_review(review_path, plan_path, engine=engine)

        bundle = self._build_bundle(
            mode="fileized",
            input_path=input_path,
            review=review,
            plan=plan,
            warnings=warnings,
        )

        self._write_json(bundle_path, bundle)
        self._write_summary(summary_path, bundle)

        return QAPipelineResult(
            mode="fileized",
            input_path=str(input_path),
            output_dir=str(self.output_dir),
            review_report_path=str(review_path),
            command_plan_report_path=str(plan_path),
            qa_bundle_path=str(bundle_path),
            run_summary_path=str(summary_path),
            violation_count=int(review.get("summary", {}).get("violation_count", 0)),
            action_candidate_count=int(review.get("summary", {}).get("action_candidate_count", 0)),
            command_plan_count=int(plan.get("summary", {}).get("plan_count", 0)),
            status="ok",
            warnings=warnings,
        )

    def run_dxf(
        self,
        dxf_path: str | Path,
        *,
        engine: str = "zwcad",
        file_id: str | None = None,
    ) -> QAPipelineResult:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        dxf_path = Path(dxf_path)

        if not dxf_path.exists():
            raise FileNotFoundError(f"DXF file does not exist: {dxf_path}")

        review_path = self.output_dir / "review_report.json"
        plan_path = self.output_dir / "command_plan_report.json"
        bundle_path = self.output_dir / "QA_BUNDLE.json"
        summary_path = self.output_dir / "RUN_SUMMARY.md"

        warnings: list[str] = []

        review = review_dxf_file(dxf_path, review_path, file_id=file_id)
        plan = command_plan_from_review(review_path, plan_path, engine=engine)

        bundle = self._build_bundle(
            mode="dxf",
            input_path=dxf_path,
            review=review,
            plan=plan,
            warnings=warnings,
        )

        self._write_json(bundle_path, bundle)
        self._write_summary(summary_path, bundle)

        return QAPipelineResult(
            mode="dxf",
            input_path=str(dxf_path),
            output_dir=str(self.output_dir),
            review_report_path=str(review_path),
            command_plan_report_path=str(plan_path),
            qa_bundle_path=str(bundle_path),
            run_summary_path=str(summary_path),
            violation_count=int(review.get("summary", {}).get("violation_count", 0)),
            action_candidate_count=int(review.get("summary", {}).get("action_candidate_count", 0)),
            command_plan_count=int(plan.get("summary", {}).get("plan_count", 0)),
            status="ok",
            warnings=warnings,
        )

    def _build_bundle(
        self,
        *,
        mode: str,
        input_path: Path,
        review: dict[str, Any],
        plan: dict[str, Any],
        warnings: list[str],
    ) -> dict[str, Any]:
        return {
            "mode": mode,
            "input_path": str(input_path),
            "review_summary": review.get("summary", {}),
            "plan_summary": plan.get("summary", {}),
            "review_report_path": str(self.output_dir / "review_report.json"),
            "command_plan_report_path": str(self.output_dir / "command_plan_report.json"),
            "review": review,
            "command_plan_report": plan,
            "warnings": warnings,
            "safety": {
                "dry_run_only": True,
                "cad_mutation": False,
                "requires_user_approval": True,
                "real_cad_execution": False,
            },
        }

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_summary(self, path: Path, bundle: dict[str, Any]) -> None:
        review_summary = bundle.get("review_summary", {}) or {}
        plan_summary = bundle.get("plan_summary", {}) or {}
        safety = bundle.get("safety", {}) or {}

        lines = [
            "# HS-CAD QA Pipeline Summary",
            "",
            f"- Mode: {bundle.get('mode')}",
            f"- Input: `{bundle.get('input_path')}`",
            f"- Violation count: {review_summary.get('violation_count', 0)}",
            f"- Action candidate count: {review_summary.get('action_candidate_count', 0)}",
            f"- Command plan count: {plan_summary.get('plan_count', 0)}",
            "",
            "## Safety",
            "",
            f"- Dry-run only: {str(safety.get('dry_run_only')).lower()}",
            f"- CAD mutation: {str(safety.get('cad_mutation')).lower()}",
            f"- Requires user approval: {str(safety.get('requires_user_approval')).lower()}",
            f"- Real CAD execution: {str(safety.get('real_cad_execution')).lower()}",
            "",
            "## Rule Summary",
            "",
        ]

        by_rule = review_summary.get("by_rule_code", {}) or {}
        if by_rule:
            for code, count in by_rule.items():
                lines.append(f"- {code}: {count}")
        else:
            lines.append("- No rule violations detected.")

        by_severity = review_summary.get("by_severity", {}) or {}
        if by_severity:
            lines += ["", "## Severity Summary", ""]
            for severity, count in by_severity.items():
                lines.append(f"- {severity}: {count}")

        warnings = bundle.get("warnings") or []
        if warnings:
            lines += ["", "## Warnings", ""]
            lines += [f"- {item}" for item in warnings]

        lines += [
            "",
            "## Generated Files",
            "",
            f"- Review report: `{bundle.get('review_report_path')}`",
            f"- Command plan report: `{bundle.get('command_plan_report_path')}`",
            "- QA bundle: `QA_BUNDLE.json`",
            "- Run summary: `RUN_SUMMARY.md`",
            "",
        ]

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
