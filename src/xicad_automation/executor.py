from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Callable, Protocol
from uuid import uuid4

from src.adapters.xicad_adapter import XiCADAdapter
from src.integrations.xicad_paths import detect_xicad_profile

from .catalog import AutomationCatalog
from .models import JobStatus, StepResult, WorkflowResult, WorkflowSpec, utc_now
from .store import JobStore


class AutomationAdapter(Protocol):
    def connect(self) -> None: ...
    def open_document(self, path: str): ...
    def run_command(self, command_text: str) -> None: ...
    def wait_until_idle(
        self,
        timeout_seconds: float = 120.0,
        poll_seconds: float = 0.2,
        cancel_check: Callable[[], bool] | None = None,
    ) -> bool: ...
    def cancel_current_command(self) -> None: ...
    def save(self) -> None: ...
    def scan_modelspace(self) -> list[dict]: ...
    def close(self) -> None: ...


class WorkflowBlocked(RuntimeError):
    pass


class WorkflowCancelled(RuntimeError):
    def __init__(self, message: str, result: WorkflowResult) -> None:
        super().__init__(message)
        self.result = result


class WorkflowExecutor:
    def __init__(self, adapter_factory: Callable[[], AutomationAdapter]) -> None:
        self.adapter_factory = adapter_factory

    def validate(self, workflow: WorkflowSpec) -> list[str]:
        problems: list[str] = []
        if not workflow.source_dwg.is_file():
            problems.append(f"Source DWG does not exist: {workflow.source_dwg}")
        profile = detect_xicad_profile(workflow.xicad_root)
        if not Path(profile.root).is_dir() or not profile.loader_candidates:
            problems.append(f"XiCAD root or loader was not detected: {workflow.xicad_root}")
        catalog = AutomationCatalog.from_xicad_root(workflow.xicad_root)
        problems.extend(catalog.validate_steps(workflow.steps))
        if not workflow.dry_run and not workflow.is_approved():
            problems.append("Approval token is missing or does not match this exact workflow")
        return problems

    @staticmethod
    def _cancelled_result(
        workflow: WorkflowSpec,
        started: str,
        steps: list[StepResult],
        recovery_path: Path | None = None,
    ) -> WorkflowResult:
        return WorkflowResult(
            workflow_id=workflow.id,
            status=JobStatus.cancelled,
            started_at=started,
            finished_at=utc_now(),
            working_dwg=str(workflow.working_dwg),
            recovery_path=str(recovery_path) if recovery_path else None,
            steps=steps,
            warnings=["Cancellation was requested; the current XiCAD command received a cancel signal."],
        )

    def execute(
        self,
        workflow: WorkflowSpec,
        cancel_check: Callable[[], bool] | None = None,
    ) -> WorkflowResult:
        started = utc_now()
        problems = self.validate(workflow)
        if problems:
            raise WorkflowBlocked("; ".join(problems))

        if cancel_check and cancel_check():
            result = self._cancelled_result(workflow, started, [])
            raise WorkflowCancelled("Cancelled before execution", result)

        if workflow.dry_run:
            return WorkflowResult(
                workflow_id=workflow.id,
                status=JobStatus.succeeded,
                started_at=started,
                finished_at=utc_now(),
                working_dwg=str(workflow.working_dwg),
                warnings=["Dry-run only: no ZWCAD or XiCAD command was executed."],
            )

        workflow.working_dwg.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workflow.source_dwg, workflow.working_dwg)
        recovery_path: Path | None = None
        if workflow.keep_recovery_copy:
            recovery_path = workflow.working_dwg.with_name(
                f"{workflow.working_dwg.stem}.recovery.{workflow.id[:8]}{workflow.working_dwg.suffix}"
            )
            shutil.copy2(workflow.working_dwg, recovery_path)

        adapter = self.adapter_factory()
        step_results: list[StepResult] = []
        try:
            adapter.connect()
            adapter.open_document(str(workflow.working_dwg))
            XiCADAdapter(adapter, str(workflow.xicad_root)).load()
            try:
                idle = adapter.wait_until_idle(timeout_seconds=120, cancel_check=cancel_check)
            except InterruptedError as exc:
                raise WorkflowCancelled(
                    str(exc), self._cancelled_result(workflow, started, step_results, recovery_path)
                ) from exc
            if not idle:
                raise TimeoutError("XiCAD bootstrap did not return ZWCAD to idle state")

            for index, step in enumerate(workflow.steps):
                if cancel_check and cancel_check():
                    raise WorkflowCancelled(
                        "Cancelled between steps",
                        self._cancelled_result(workflow, started, step_results, recovery_path),
                    )
                step_started = utc_now()
                before_count = len(adapter.scan_modelspace())
                checkpoint_path: Path | None = None
                try:
                    adapter.run_command(step.command_text())
                    try:
                        idle = adapter.wait_until_idle(
                            timeout_seconds=step.timeout_seconds,
                            cancel_check=cancel_check,
                        )
                    except InterruptedError as exc:
                        step_results.append(
                            StepResult(
                                index=index,
                                alias=step.alias,
                                status="cancelled",
                                started_at=step_started,
                                finished_at=utc_now(),
                                before_count=before_count,
                                error=str(exc),
                            )
                        )
                        raise WorkflowCancelled(
                            str(exc),
                            self._cancelled_result(workflow, started, step_results, recovery_path),
                        ) from exc
                    if not idle:
                        adapter.cancel_current_command()
                        raise TimeoutError(f"{step.alias} exceeded {step.timeout_seconds:.0f}s")
                    after_count = len(adapter.scan_modelspace())
                    delta = after_count - before_count
                    if step.expected_min_entity_delta is not None and delta < step.expected_min_entity_delta:
                        raise RuntimeError(
                            f"{step.alias} entity delta {delta} is below expected {step.expected_min_entity_delta}"
                        )
                    if workflow.save_after_each_step:
                        adapter.save()
                    if step.checkpoint and workflow.working_dwg.is_file():
                        checkpoint_path = workflow.working_dwg.with_name(
                            f"{workflow.working_dwg.stem}.step-{index + 1:03d}-{step.alias}{workflow.working_dwg.suffix}"
                        )
                        shutil.copy2(workflow.working_dwg, checkpoint_path)
                    step_results.append(
                        StepResult(
                            index=index,
                            alias=step.alias,
                            status="succeeded",
                            started_at=step_started,
                            finished_at=utc_now(),
                            before_count=before_count,
                            after_count=after_count,
                            checkpoint_path=str(checkpoint_path) if checkpoint_path else None,
                        )
                    )
                except WorkflowCancelled:
                    raise
                except Exception as exc:
                    step_results.append(
                        StepResult(
                            index=index,
                            alias=step.alias,
                            status="failed",
                            started_at=step_started,
                            finished_at=utc_now(),
                            before_count=before_count,
                            error=str(exc),
                        )
                    )
                    raise

            adapter.save()
            return WorkflowResult(
                workflow_id=workflow.id,
                status=JobStatus.succeeded,
                started_at=started,
                finished_at=utc_now(),
                working_dwg=str(workflow.working_dwg),
                recovery_path=str(recovery_path) if recovery_path else None,
                steps=step_results,
            )
        except WorkflowCancelled:
            try:
                adapter.cancel_current_command()
            except Exception:
                pass
            raise
        except Exception:
            try:
                adapter.cancel_current_command()
            except Exception:
                pass
            raise
        finally:
            try:
                adapter.close()
            except Exception:
                pass


class BackgroundWorker:
    """Single-thread COM worker consuming the persistent queue."""

    def __init__(self, store: JobStore, executor: WorkflowExecutor, worker_id: str | None = None) -> None:
        self.store = store
        self.executor = executor
        self.worker_id = worker_id or f"xicad-worker-{uuid4().hex[:8]}"

    def run_once(self) -> bool:
        job = self.store.claim_next(self.worker_id)
        if job is None:
            return False
        try:
            problems = self.executor.validate(job.workflow)
            if problems:
                self.store.block(job.id, "; ".join(problems))
                return True
            result = self.executor.execute(
                job.workflow,
                cancel_check=lambda: self.store.is_cancellation_requested(job.id),
            )
            self.store.complete(job.id, result)
        except WorkflowCancelled as exc:
            self.store.complete(job.id, exc.result)
        except WorkflowBlocked as exc:
            self.store.block(job.id, str(exc))
        except Exception as exc:
            self.store.fail(job.id, str(exc))
        return True

    def run_forever(self, poll_seconds: float = 2.0) -> None:
        pythoncom = None
        try:
            import pythoncom as _pythoncom

            pythoncom = _pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            pass
        try:
            self.store.recover_abandoned()
            while True:
                if not self.run_once():
                    time.sleep(max(0.2, poll_seconds))
        finally:
            if pythoncom is not None:
                pythoncom.CoUninitialize()
