from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables
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


def test_create_coding_job_returns_job_id(app_client, workspace):
    response = app_client.post(
        "/projects/demo/coding-jobs",
        json={
            "analysis_run_id": "run-1",
            "question_column": "Q1",
            "responses": [f"resp {i}" for i in range(100)],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["total_batches"] >= 1


def test_get_coding_job_status_returns_progress(app_client, workspace):
    create_resp = app_client.post(
        "/projects/demo/coding-jobs",
        json={
            "analysis_run_id": "run-1",
            "question_column": "Q1",
            "responses": ["resp 1", "resp 2"],
        },
    )
    job_id = create_resp.json()["job_id"]

    status_resp = app_client.get(f"/projects/demo/coding-jobs/{job_id}/status")

    assert status_resp.status_code == 200
    data = status_resp.json()
    assert "status" in data
    assert "total_batches" in data
    assert "completed_batches" in data


def test_cancel_coding_job(app_client, workspace):
    create_resp = app_client.post(
        "/projects/demo/coding-jobs",
        json={
            "analysis_run_id": "run-1",
            "question_column": "Q1",
            "responses": ["resp 1"],
        },
    )
    job_id = create_resp.json()["job_id"]

    cancel_resp = app_client.post(f"/projects/demo/coding-jobs/{job_id}/cancel")

    assert cancel_resp.status_code == 200

    status_resp = app_client.get(f"/projects/demo/coding-jobs/{job_id}/status")
    assert status_resp.json()["status"] == "cancelled"
