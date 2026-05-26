import json
from pathlib import Path

from src.remote_worker.worker_runner import run_job


def test_worker_runner_creates_outputs(tmp_path: Path):
    job_path = tmp_path / "job.json"
    job_path.write_text(
        json.dumps(
            {
                "job_id": "demo",
                "output_dir": str(tmp_path / "outputs"),
                "source": {"type": "local", "file_path": str(tmp_path / "missing.dxf"), "allow_blank": True},
                "actions": [
                    {
                        "type": "add_text_note",
                        "layer": "DIMLE",
                        "text": "외벽: T100 그라스울 판넬",
                        "position": [100, 100],
                    }
                ],
                "outputs": ["dxf", "svg", "png", "change_report"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out_dir = run_job(job_path)
    assert (out_dir / "modified.dxf").exists()
    assert (out_dir / "preview.svg").exists()
    assert (out_dir / "preview.png").exists()
    assert (out_dir / "change_report.md").exists()
