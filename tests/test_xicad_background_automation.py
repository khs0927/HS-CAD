from __future__ import annotations

from pathlib import Path

import pytest

from src.xicad_automation.catalog import AutomationCatalog
from src.xicad_automation.contracts import ContractLibrary, PromptContract
from src.xicad_automation.executor import BackgroundWorker, WorkflowExecutor
from src.xicad_automation.models import CommandStep, JobStatus, WorkflowResult, WorkflowSpec, utc_now
from src.xicad_automation.store import JobStore
from src.xicad_automation.workflows import (
    ArchitecturalDrawingSpec,
    ArchitecturalElement,
    ArchitecturalWorkflowCompiler,
)


def make_xicad_root(tmp_path: Path, alias: str = "ZZZ") -> Path:
    root = tmp_path / "XiCAD"
    lisp = root / "Lisp"
    lisp.mkdir(parents=True)
    (lisp / "xi.zelx").write_text("fixture", encoding="utf-8")
    (lisp / "xiShortkey_origin.key").write_text(f"{alias}, custom command\n", encoding="utf-8")
    return root


def make_workflow(tmp_path: Path, *, dry_run: bool = True) -> WorkflowSpec:
    source = tmp_path / "source.dwg"
    source.write_bytes(b"DWG fixture")
    return WorkflowSpec(
        name="test",
        source_dwg=source,
        working_dwg=tmp_path / "working.dwg",
        xicad_root=make_xicad_root(tmp_path),
        dry_run=dry_run,
        steps=[CommandStep(alias="ZZZ", arguments=["1", "2"], allow_interactive=True)],
    )


def test_approval_token_is_bound_to_exact_workflow(tmp_path: Path):
    workflow = make_workflow(tmp_path, dry_run=False)
    token = workflow.expected_approval_token()
    workflow.approval_token = token
    assert workflow.is_approved()
    workflow.steps[0].arguments.append("changed")
    assert not workflow.is_approved()


def test_store_claim_complete_and_reopen(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    queued = store.enqueue(make_workflow(tmp_path))
    claimed = store.claim_next("worker-1")
    assert claimed is not None
    assert claimed.id == queued.id
    assert claimed.status == JobStatus.running
    assert claimed.attempts == 1

    result = WorkflowResult(
        workflow_id=claimed.workflow.id,
        status=JobStatus.succeeded,
        started_at=utc_now(),
        finished_at=utc_now(),
        working_dwg=str(claimed.workflow.working_dwg),
    )
    completed = store.complete(claimed.id, result)
    assert completed.status == JobStatus.succeeded
    assert JobStore(store.path).get(claimed.id).result is not None


def test_catalog_discovers_all_shortcut_aliases(tmp_path: Path):
    root = make_xicad_root(tmp_path, alias="XYZ")
    rows = AutomationCatalog.from_xicad_root(root).describe()
    assert any(row["alias"] == "XYZ" for row in rows)


def test_architectural_compiler_uses_verified_contracts(tmp_path: Path):
    contract = PromptContract(
        alias="WAL",
        argument_templates=["{start}", "{end}", "{thickness}"],
        verified=True,
    )
    drawing = ArchitecturalDrawingSpec(
        source_dwg=tmp_path / "source.dwg",
        working_dwg=tmp_path / "working.dwg",
        xicad_root=tmp_path / "XiCAD",
        elements=[
            ArchitecturalElement(
                kind="wall",
                alias="WAL",
                parameters={"start": "0,0", "end": "5000,0", "thickness": 200},
            )
        ],
    )
    workflow = ArchitecturalWorkflowCompiler(ContractLibrary([contract])).compile(drawing)
    assert workflow.steps[0].arguments == ["0,0", "5000,0", "200"]
    assert workflow.steps[0].command_text() == "WAL\n0,0\n5000,0\n200\n"


def test_architectural_compiler_rejects_unverified_contract(tmp_path: Path):
    drawing = ArchitecturalDrawingSpec(
        source_dwg=tmp_path / "source.dwg",
        working_dwg=tmp_path / "working.dwg",
        xicad_root=tmp_path / "XiCAD",
        elements=[ArchitecturalElement(kind="door", alias="D1", parameters={})],
    )
    with pytest.raises(ValueError, match="not verified"):
        ArchitecturalWorkflowCompiler(ContractLibrary([PromptContract(alias="D1")])).compile(drawing)


def test_dry_run_validates_without_starting_adapter(tmp_path: Path):
    workflow = make_workflow(tmp_path, dry_run=True)

    def forbidden_factory():
        raise AssertionError("adapter must not start in dry-run")

    executor = WorkflowExecutor(forbidden_factory)
    assert executor.validate(workflow) == []
    result = executor.execute(workflow)
    assert result.status == JobStatus.succeeded
    assert "Dry-run" in result.warnings[0]


def test_worker_blocks_unapproved_live_job(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    workflow = make_workflow(tmp_path, dry_run=False)
    queued = store.enqueue(workflow)
    worker = BackgroundWorker(store, WorkflowExecutor(lambda: None))
    assert worker.run_once()
    record = store.get(queued.id)
    assert record.status == JobStatus.blocked
    assert "Approval token" in (record.error or "")
