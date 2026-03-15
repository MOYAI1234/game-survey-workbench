from pathlib import Path
import sqlite3

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
    assert "生成草稿" in html or "问卷设计" in html


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


def test_questionnaire_page_loads_with_legacy_db_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    (tmp_path / "knowledge").mkdir(parents=True, exist_ok=True)
    (tmp_path / "projects").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)

    database_path = tmp_path / "app.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE questionnairespecversion (
                id INTEGER PRIMARY KEY,
                project_slug VARCHAR NOT NULL,
                version_id VARCHAR NOT NULL UNIQUE,
                research_goal VARCHAR NOT NULL,
                markdown_spec VARCHAR NOT NULL,
                created_at TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO questionnairespecversion
            (project_slug, version_id, research_goal, markdown_spec, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                "legacy-questionnaire",
                "v1",
                "Understand player motivation",
                "# Legacy Draft\n\n1. Favorite mode?",
            ),
        )
        connection.commit()

    with TestClient(create_app()) as client:
        response = client.get("/projects/legacy-questionnaire/questionnaires/latest")

    assert response.status_code == 200
    assert "Legacy Draft" in response.text


def test_questionnaire_draft_form_degrades_without_any_knowledge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")

    with TestClient(create_app()) as client:
        client.post(
            "/projects",
            json={"slug": "no-kb", "name": "No Knowledge"},
        )

        response = client.post(
            "/projects/no-kb/questionnaires/draft-form",
            data={"research_goal": "Understand new user onboarding"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        latest_page = client.get("/projects/no-kb/questionnaires/latest")

    assert latest_page.status_code == 200
    assert "已先基于研究简报和输入生成基础版本" in latest_page.text
    assert "Understand new user onboarding" in latest_page.text


def test_questionnaire_draft_form_degrades_when_no_design_knowledge_matches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    source = tmp_path / "analysis-only.md"
    source.write_text(
        "---\n"
        "title: Analysis Only Guide\n"
        "doc_type: guide\n"
        "stage:\n"
        "  - analysis\n"
        "---\n"
        "# Analysis Only Guide\n\nOnly analysis guidance.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)

    with TestClient(create_app()) as client:
        client.post(
            "/projects",
            json={"slug": "analysis-only", "name": "Analysis Only"},
        )

        response = client.post(
            "/projects/analysis-only/questionnaires/draft-form",
            data={"research_goal": "Evaluate monetization sentiment"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        latest_page = client.get("/projects/analysis-only/questionnaires/latest")

    assert latest_page.status_code == 200
    assert "当前未匹配到相关知识" in latest_page.text
    assert "Evaluate monetization sentiment" in latest_page.text
