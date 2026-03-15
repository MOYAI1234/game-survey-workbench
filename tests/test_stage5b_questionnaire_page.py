from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def project_slug(client, tmp_path):
    slug = "quest-page-test"
    client.post("/projects", json={"slug": slug, "name": "Questionnaire Page Test"})
    source = tmp_path / "guide.md"
    source.write_text(
        "---\ntitle: Survey Guide\ndoc_type: guide\nstage:\n  - design\nscenario: quest-page-test\npriority: 1\n---\n# Guide\nDesign guidance.",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)
    return slug


def test_questionnaire_page_has_draft_form(client, project_slug):
    response = client.get(f"/projects/{project_slug}/questionnaires/latest")

    assert response.status_code == 200
    html = response.text
    assert 'name="research_goal"' in html
    assert "Generate" in html or "Draft" in html


def test_questionnaire_draft_form_submission(client, project_slug):
    response = client.post(
        f"/projects/{project_slug}/questionnaires/draft-form",
        data={"research_goal": "Understand player motivation"},
        follow_redirects=False,
    )

    assert response.status_code in (201, 302, 303)


def test_questionnaire_page_shows_latest_draft(client, project_slug):
    client.post(
        f"/projects/{project_slug}/questionnaires/draft",
        json={"research_goal": "Player satisfaction"},
    )

    response = client.get(f"/projects/{project_slug}/questionnaires/latest")

    html = response.text
    assert (
        "questionnaire-content" in html
        or "markdown" in html.lower()
        or "Knowledge Basis" in html
        or "Player" in html
    )
