from __future__ import annotations

import importlib
from typing import Any

from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.registry import WorkerRegistry


class WorkerRunner:
    def __init__(self, registry: WorkerRegistry):
        self.registry = registry

    def dry_run(self, worker_name: str, worker_input: WorkerInput) -> dict[str, Any]:
        spec = self.registry.get(worker_name)
        if spec is None:
            return {
                "worker_name": worker_name,
                "status": "unavailable",
                "reason": "worker is not registered in manifest",
            }
        return {
            "worker_name": worker_name,
            "status": "planned",
            "module": spec.path,
            "task": worker_input.task,
            "workspace": worker_input.workspace,
            "input_artifact_count": len(worker_input.input_artifacts),
        }

    def run(self, worker_name: str, worker_input: WorkerInput) -> WorkerOutput:
        spec = self.registry.get(worker_name)
        if spec is None:
            return WorkerOutput.unavailable(
                worker_name=worker_name,
                backend="worker_registry",
                message="worker is not registered in manifest",
            )

        try:
            module = importlib.import_module(spec.path)
        except Exception as exc:
            return WorkerOutput.error(
                worker_name=worker_name,
                backend=spec.path,
                message=f"failed to import worker module: {exc}",
            )

        run_worker = getattr(module, "run_worker", None)
        if run_worker is None:
            return WorkerOutput.error(
                worker_name=worker_name,
                backend=spec.path,
                message="worker module does not expose run_worker",
            )

        output = run_worker(worker_input)
        if isinstance(output, WorkerOutput):
            return output
        if isinstance(output, dict):
            return WorkerOutput(
                worker_name=worker_name,
                backend=spec.path,
                status=str(output.get("status") or "ok"),
                artifacts=[str(item) for item in output.get("artifacts") or []],
                warnings=[str(item) for item in output.get("warnings") or []],
                metrics=dict(output.get("metrics") or {}),
            )
        return WorkerOutput.error(
            worker_name=worker_name,
            backend=spec.path,
            message=f"worker returned unsupported output type: {type(output).__name__}",
        )
