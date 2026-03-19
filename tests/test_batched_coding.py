import json
from pathlib import Path
from unittest.mock import MagicMock

from game_survey_workbench.db import create_db_and_tables
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.batched_coding import (
    create_coding_job,
    deduplicate_responses,
    get_coding_job_status,
    run_coding_job,
)
from game_survey_workbench.services.projects import create_project


def _fake_llm_response(themes=None):
    if themes is None:
        themes = [{"theme_name": "Positive", "count": 2, "example_responses": ["good", "great"]}]
    return json.dumps({"themes": themes, "uncoded_count": 0})


def test_deduplicate_responses_removes_exact_duplicates():
    unique, mapping = deduplicate_responses(["a", "b", "a", "c", "b", "a"])

    assert unique == ["a", "b", "c"]
    assert mapping["a"] == [0, 2, 5]
    assert mapping["b"] == [1, 4]
    assert mapping["c"] == [3]


def test_create_coding_job_splits_into_correct_number_of_batches(tmp_path: Path):
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)
    responses = [f"response {i}" for i in range(200)]

    job, batches = create_coding_job(
        workspace_root=tmp_path,
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        batch_size=80,
    )

    assert job.status == "queued"
    assert job.total_responses == 200
    assert len(batches) == 3
    assert all(batch.status == "pending" for batch in batches)


def test_small_dataset_creates_single_batch(tmp_path: Path):
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)
    responses = [f"response {i}" for i in range(50)]

    _job, batches = create_coding_job(
        workspace_root=tmp_path,
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        batch_size=80,
    )

    assert len(batches) == 1


def test_run_coding_job_completes_all_batches(tmp_path: Path):
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)
    responses = [f"response {i}" for i in range(160)]
    mock_client = MagicMock()
    mock_client.generate.return_value = _fake_llm_response()

    job, _batches = create_coding_job(
        workspace_root=tmp_path,
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        batch_size=80,
    )

    run_coding_job(
        workspace_root=tmp_path,
        job_id=job.id,
        client=mock_client,
    )

    status = get_coding_job_status(workspace_root=tmp_path, job_id=job.id)
    assert status["status"] == "done"
    assert status["completed_batches"] == 2
    assert status["total_batches"] == 2
    assert mock_client.generate.call_count == 2


def test_run_coding_job_handles_batch_failure_gracefully(tmp_path: Path):
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)
    responses = [f"response {i}" for i in range(160)]
    mock_client = MagicMock()
    mock_client.generate.side_effect = [
        _fake_llm_response(),
        Exception("API error"),
        Exception("API error"),
        Exception("API error"),
    ]

    job, _batches = create_coding_job(
        workspace_root=tmp_path,
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        batch_size=80,
    )

    run_coding_job(
        workspace_root=tmp_path,
        job_id=job.id,
        client=mock_client,
    )

    status = get_coding_job_status(workspace_root=tmp_path, job_id=job.id)
    assert status["status"] == "partial"
    assert status["completed_batches"] == 1
    assert status["failed_batches"] == 1
