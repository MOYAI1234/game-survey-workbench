from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion
from game_survey_workbench.services.workspace import bootstrap_workspace

SAMPLE_MARKDOWN = """\
## Section One

- Question 1: What do you think?
  > Diagnostic: measures satisfaction

## Section Two

- Question 2: How often do you play?
"""


@pytest.fixture()
def workspace_with_questionnaire(tmp_path: Path) -> tuple[Path, str]:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        session.add(ProjectRecord(slug="demo", name="Demo"))
        version = QuestionnaireSpecVersion(
            project_slug="demo",
            version_id="v-test-1",
            research_goal="Test goal",
            markdown_spec=SAMPLE_MARKDOWN,
        )
        session.add(version)
        session.commit()
    return tmp_path, "v-test-1"


@pytest.fixture()
def app_client(workspace_with_questionnaire, monkeypatch):
    workspace, _ = workspace_with_questionnaire
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as client:
        yield client


def test_download_questionnaire_as_md(app_client, workspace_with_questionnaire):
    _, version_id = workspace_with_questionnaire
    response = app_client.get(
        f"/projects/demo/questionnaires/{version_id}/download?fmt=md"
    )
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "## Section One" in response.text
    assert "attachment" in response.headers.get("content-disposition", "")


def test_download_questionnaire_as_txt(app_client, workspace_with_questionnaire):
    _, version_id = workspace_with_questionnaire
    response = app_client.get(
        f"/projects/demo/questionnaires/{version_id}/download?fmt=txt"
    )
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "##" not in response.text
    assert "Section One" in response.text
    assert "Question 1" in response.text


def test_download_questionnaire_returns_404_for_unknown_version(app_client):
    response = app_client.get(
        "/projects/demo/questionnaires/nonexistent/download"
    )
    assert response.status_code == 404


def test_download_defaults_to_md_when_fmt_missing(app_client, workspace_with_questionnaire):
    _, version_id = workspace_with_questionnaire
    response = app_client.get(
        f"/projects/demo/questionnaires/{version_id}/download"
    )
    assert response.status_code == 200
    assert "## Section One" in response.text
