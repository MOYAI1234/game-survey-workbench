from pathlib import Path

from sqlmodel import Session

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.coding_job import CodingBatch, CodingJob


def test_coding_job_and_batch_persist_and_load(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        job = CodingJob(
            project_slug="demo",
            analysis_run_id="run-1",
            question_column="Q1",
            status="queued",
            total_responses=100,
            coded_responses=0,
            batch_size=80,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.id is not None

        batch = CodingBatch(
            job_id=job.id,
            batch_index=0,
            status="pending",
            input_texts_json=["resp1", "resp2"],
        )
        session.add(batch)
        session.commit()
        session.refresh(batch)

        assert batch.id is not None
        assert batch.job_id == job.id


def test_coding_job_status_transitions(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        job = CodingJob(
            project_slug="demo",
            analysis_run_id="run-1",
            question_column="Q1",
            status="queued",
            total_responses=50,
            coded_responses=0,
            batch_size=80,
        )
        session.add(job)
        session.commit()

        job.status = "running"
        job.coded_responses = 25
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.status == "running"
        assert job.coded_responses == 25
