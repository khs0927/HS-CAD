from __future__ import annotations

import json
from pathlib import Path

from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.registry import WorkerRegistry
from src.workers.runner import WorkerRunner


def test_worker_input_round_trips_from_json_file(tmp_path: Path):
    path = tmp_path / "worker_input.json"
    path.write_text(
        json.dumps(
            {
                "worker_name": "example_worker",
                "task": "run",
                "workspace": "outputs/example",
                "input_artifacts": ["a.json"],
                "options": {"dry_run": True},
            }
        ),
        encoding="utf-8",
    )

    worker_input = WorkerInput.from_json_file(path)

    assert worker_input.worker_name == "example_worker"
    assert worker_input.input_artifacts == ["a.json"]
    assert worker_input.options["dry_run"] is True
    assert json.loads(worker_input.to_json())["workspace"] == "outputs/example"


def test_worker_output_error_shape_is_json_serializable():
    output = WorkerOutput.error(
        worker_name="missing_worker",
        backend="worker_registry",
        message="not registered",
    )

    payload = json.loads(output.to_json())
    assert payload["status"] == "error"
    assert payload["error"] == "not registered"


def test_worker_registry_and_runner_dry_run(tmp_path: Path):
    manifest = tmp_path / "worker_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "workers": {
                    "example_worker": {
                        "path": "src.workers.example_worker",
                        "description": "fixture worker",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    registry = WorkerRegistry(manifest)
    runner = WorkerRunner(registry)
    worker_input = WorkerInput(worker_name="example_worker", task="run", workspace=str(tmp_path))

    assert registry.names() == ["example_worker"]
    planned = runner.dry_run("example_worker", worker_input)
    missing = runner.dry_run("missing_worker", worker_input)

    assert planned["status"] == "planned"
    assert missing["status"] == "unavailable"
