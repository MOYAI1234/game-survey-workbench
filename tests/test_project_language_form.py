from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.services.projects import get_project
from game_survey_workbench.services.workspace import bootstrap_workspace


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        session.add(ProjectRecord(slug="demo", name="Demo", language="zh"))
        session.commit()
    return tmp_path


@pytest.fixture()
def app_client(workspace, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as client:
        yield client


def test_project_page_shows_language_selector(app_client):
    response = app_client.get("/projects/demo")
    html = response.text
    assert "language" in html.lower()
    assert 'value="zh"' in html
    assert 'value="en"' in html


def test_project_settings_form_updates_language(app_client, workspace):
    response = app_client.post(
        "/projects/demo/settings",
        data={"language": "en"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    project = get_project(workspace_root=workspace, project_slug="demo")
    assert project is not None
    assert project.language == "en"
