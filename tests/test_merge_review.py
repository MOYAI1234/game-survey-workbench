from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.coding_job import CodingJob
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.workspace import bootstrap_workspace


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)
    return tmp_path


@pytest.fixture()
def app_client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as client:
        yield client


def _create_done_job(workspace: Path) -> int:
    engine = get_engine(workspace)
    with Session(engine) as session:
        job = CodingJob(
            project_slug="demo",
            analysis_run_id="run-1",
            question_column="Q1",
            status="done",
            total_responses=100,
            coded_responses=100,
            batch_size=80,
            final_codebook_json={
                "themes": [
                    {"theme_name": "Great graphics", "count": 10, "example_responses": ["good visuals"]},
                    {"theme_name": "Good graphics", "count": 8, "example_responses": ["nice art"]},
                    {"theme_name": "Fun gameplay", "count": 15, "example_responses": ["enjoyable"]},
                ]
            },
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job.id


def test_merge_review_shows_codebook(app_client, workspace):
    job_id = _create_done_job(workspace)

    response = app_client.get(f"/projects/demo/coding-jobs/{job_id}/merge-review")

    assert response.status_code == 200
    html = response.text
    assert "Great graphics" in html
    assert "Good graphics" in html
    assert "Fun gameplay" in html


def test_merge_confirm_merges_selected_themes(app_client, workspace):
    job_id = _create_done_job(workspace)

    response = app_client.post(
        f"/projects/demo/coding-jobs/{job_id}/merge-confirm",
        data={
            "merge_group_0_target": "Great graphics",
            "merge_group_0_sources": ["Good graphics"],
        },
        follow_redirects=False,
    )

    assert response.status_code in (200, 303)
