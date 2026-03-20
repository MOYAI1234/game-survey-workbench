from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def client_with_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        session.add(ProjectRecord(slug="sp", name="Spinner Test"))
        session.add(
            QuestionnaireSpecVersion(
                project_slug="sp",
                version_id="v1",
                research_goal="test",
                markdown_spec="# Q\n\n1. Question",
            )
        )
        session.commit()
    with TestClient(create_app()) as test_client:
        yield test_client


def test_questionnaire_draft_button_has_loading_text(client: TestClient):
    client.post("/projects", json={"slug": "sp1", "name": "SP1"})
    response = client.get("/projects/sp1/questionnaires/latest")
    html = response.text
    assert 'data-loading-text=' in html


def test_questionnaire_refine_button_has_loading_text(client_with_project):
    response = client_with_project.get("/projects/sp/questionnaires/latest")
    html = response.text
    assert html.count("data-loading-text=") >= 2


def test_analysis_buttons_have_loading_text(client: TestClient):
    client.post("/projects", json={"slug": "sp2", "name": "SP2"})
    csv_content = (
        "Q1_Satisfaction,Q2_Feedback\n"
        "scale,free_text\n"
        "5,Love it\n"
        "3,Needs work\n"
    )
    import_response = client.post(
        "/projects/sp2/datasets/import",
        files={"file": ("survey.csv", csv_content.encode(), "text/csv")},
    )
    assert import_response.status_code == 201
    analysis_response = client.get("/projects/sp2/analysis/latest")
    html = analysis_response.text
    assert "data-loading-text=" in html


def test_non_llm_buttons_do_not_have_loading_text(client: TestClient):
    response = client.get("/")
    html = response.text
    assert html.count("data-loading-text=") == 0
