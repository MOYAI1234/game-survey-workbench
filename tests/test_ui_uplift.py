from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion
from game_survey_workbench.routes import questionnaires


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    with TestClient(create_app()) as test_client:
        yield test_client


def test_questionnaire_templates_register_markdown_filter():
    assert "markdown" in questionnaires.templates.env.filters


def test_questionnaire_content_not_in_pre_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        session.add(ProjectRecord(slug="md-test", name="Markdown Test"))
        session.add(
            QuestionnaireSpecVersion(
                project_slug="md-test",
                version_id="v1",
                research_goal="Render markdown",
                markdown_spec="# Heading\n\n- bullet",
            )
        )
        session.commit()

    with TestClient(create_app()) as test_client:
        response = test_client.get("/projects/md-test/questionnaires/latest")

    assert response.status_code == 200
    html = response.text
    assert '<pre class="questionnaire-markdown">' not in html
    assert 'class="prose questionnaire-rendered"' in html
