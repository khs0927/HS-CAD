from src.remote_worker.job_schema import RemoteDxfJob


def test_job_schema_accepts_add_leader_note():
    job = RemoteDxfJob.model_validate(
        {
            "job_id": "demo",
            "source": {"type": "local", "allow_blank": True},
            "actions": [
                {
                    "type": "add_leader_note",
                    "layer": "DIMLE",
                    "text": "기초: 매트기초",
                    "position": [100, 200],
                    "leader_to": [50, 80],
                }
            ],
        }
    )
    assert job.job_id == "demo"
    assert job.actions[0].type == "add_leader_note"
