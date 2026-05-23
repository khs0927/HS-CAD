from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.registry import WorkerRegistry, WorkerSpec


class WorkerRunner:
    def __init__(self, registry: WorkerRegistry | None = None):
        self.registry = registry or WorkerRegistry()

    def command_for(self, spec: WorkerSpec, input_path: str | Path) -> list[str]:
        entry = spec.entry.strip()
        if not entry:
            raise ValueError(f'Worker {spec.name} has empty entry')
        if spec.env_manager == 'current_python':
            return _python_entry_command(entry, input_path)
        if spec.env_manager == 'uv':
            return _uv_entry_command(spec, input_path)
        raise ValueError(f'Unsupported env_manager for worker {spec.name}: {spec.env_manager}')

    def run(self, worker_name: str, worker_input: WorkerInput) -> WorkerOutput:
        spec = self.registry.get(worker_name)
        if spec is None:
            return WorkerOutput.error(
                worker_name=worker_name,
                backend=worker_name,
                message=f'worker not found in manifest: {worker_name}',
                status='unavailable',
            )
        if spec.status != 'implemented':
            return WorkerOutput.error(
                worker_name=worker_name,
                backend=worker_name,
                message=f'worker is not implemented yet: {spec.status}',
                status='unavailable',
            )
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / 'worker_input.json'
            worker_input.write_json(input_path)
            command = self.command_for(spec, input_path)
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=spec.timeout_sec,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return WorkerOutput.error(
                    worker_name=worker_name,
                    backend=worker_name,
                    message=f'worker timed out after {spec.timeout_sec}s',
                    status='timeout',
                )
            if result.returncode != 0:
                return WorkerOutput.error(
                    worker_name=worker_name,
                    backend=worker_name,
                    message=(result.stderr or result.stdout or f'worker exited with {result.returncode}')[:4000],
                )
            return _parse_worker_stdout(worker_name, result.stdout)

    def dry_run(self, worker_name: str, worker_input: WorkerInput) -> dict[str, Any]:
        spec = self.registry.get(worker_name)
        if spec is None:
            return {'status': 'unavailable', 'reason': f'worker not found: {worker_name}'}
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / 'worker_input.json'
            worker_input.write_json(input_path)
            return {
                'worker': spec.to_dict(),
                'command': self.command_for(spec, input_path),
                'input': worker_input.model_dump(),
            }


def _python_entry_command(entry: str, input_path: str | Path) -> list[str]:
    parts = entry.split()
    if parts[:3] == ['python', '-m']:
        return [sys.executable, '-m', parts[2], str(input_path)]
    return parts + [str(input_path)]


def _uv_entry_command(spec: WorkerSpec, input_path: str | Path) -> list[str]:
    command = ['uv', 'run']
    for req in spec.requirements:
        command.extend(['--with', req])
    parts = spec.entry.split()
    if parts[:3] == ['python', '-m']:
        command.extend(['python', '-m', parts[2], str(input_path)])
    else:
        command.extend(parts + [str(input_path)])
    return command


def _parse_worker_stdout(worker_name: str, stdout: str) -> WorkerOutput:
    text = stdout.strip()
    if not text:
        return WorkerOutput.error(
            worker_name=worker_name,
            backend=worker_name,
            message='worker produced empty stdout',
        )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        # Some workers may print logs before the final JSON. Try last line.
        try:
            payload = json.loads(text.splitlines()[-1])
        except Exception:
            return WorkerOutput.error(
                worker_name=worker_name,
                backend=worker_name,
                message='worker stdout was not valid JSON',
            )
    return WorkerOutput.model_validate(payload)
