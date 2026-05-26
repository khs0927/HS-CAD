import pytest

from src.remote_worker.job_schema import RemoteDxfJob
from src.remote_worker.safety_guard import validate_job_safety


def test_safety_guard_requires_position_for_note():
    job = RemoteDxfJob.model_validate(
        {
            "job_id": "demo",
            "source": {"type": "local", "allow_blank": True},
            "actions": [{"type": "add_text_note", "text": "note"}],
        }
    )
    with pytest.raises(ValueError):
        validate_job_safety(job)
