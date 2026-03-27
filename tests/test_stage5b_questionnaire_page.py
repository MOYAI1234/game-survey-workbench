from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.models.questionnaire import QuestionnaireDraftRequest
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)
from game_survey_workbench.services.questionnaires import save_questionnaire_draft
from game_survey_workbench.services.research_waves import create_research_wave


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
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug=slug,
        knowledge_document_ids=[1],
    )
    return slug


def test_questionnaire_page_has_draft_form(client, project_slug):
    response = client.get(f"/projects/{project_slug}/questionnaires/latest")

    assert response.status_code == 200
    html = response.text
    assert "questionnaire-workspace" in html
    assert "questionnaire-sidebar" in html
    assert "data-running-message=" in html
    assert "data-sidebar-open" in html
    assert "data-sidebar-close" in html
    assert "status-summary-card" in html
    assert "status-token" in html
    assert "empty-state-card" in html
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
    assert "最新草稿" in html
    assert "questionnaire-content" in html


def test_questionnaire_latest_page_is_scoped_to_current_wave(client, tmp_path):
    client.post("/projects", json={"slug": "demo", "name": "Demo"})
    wave_one = create_research_wave(
        workspace_root=tmp_path,
        project_slug="demo",
        name="1.0 版本问卷",
    )
    wave_two = create_research_wave(
        workspace_root=tmp_path,
        project_slug="demo",
        name="1.1 版本问卷",
    )

    save_questionnaire_draft(
        project_slug="demo",
        project_name="Demo",
        payload=QuestionnaireDraftRequest(research_goal="Wave 1 goal"),
        workspace_root=tmp_path,
        wave_id=wave_one.id,
        markdown_spec="# Wave 1",
    )
    save_questionnaire_draft(
        project_slug="demo",
        project_name="Demo",
        payload=QuestionnaireDraftRequest(research_goal="Wave 2 goal"),
        workspace_root=tmp_path,
        wave_id=wave_two.id,
        markdown_spec="# Wave 2",
    )

    response = client.get("/projects/demo/questionnaires/latest")

    assert "Wave 2" in response.text
    assert "Wave 1" not in response.text


def test_questionnaire_page_shows_retrieval_pool_metadata_for_used_knowledge(
    client,
    project_slug,
):
    client.post(
        f"/projects/{project_slug}/questionnaires/draft",
        json={"research_goal": "Player satisfaction"},
    )

    response = client.get(f"/projects/{project_slug}/questionnaires/latest")

    assert response.status_code == 200
    html = response.text
    assert "Survey Guide" in html
    assert "方法论池" in html
    assert "参考知识来源" in html


def test_questionnaire_page_hides_knowledge_basis_body_from_main_content(client, tmp_path):
    client.post("/projects", json={"slug": "demo", "name": "Demo"})
    wave = create_research_wave(
        workspace_root=tmp_path,
        project_slug="demo",
        name="1.1 版本问卷",
    )

    save_questionnaire_draft(
        project_slug="demo",
        project_name="Demo",
        payload=QuestionnaireDraftRequest(research_goal="Wave 2 goal"),
        workspace_root=tmp_path,
        wave_id=wave.id,
        markdown_spec=(
            "# Questionnaire Draft\n\n"
            "## Core Questions\n- Q1\n\n"
            "## Knowledge Basis\n"
            "- Survey Guide: 这一大段原始知识正文不应该直接出现在主阅读区。"
        ),
        retrieved_snippets=[
            {
                "document_title": "Survey Guide",
                "retrieval_pool": "method",
                "content": "这一大段原始知识正文不应该直接出现在主阅读区。",
            }
        ],
    )

    response = client.get("/projects/demo/questionnaires/latest")

    assert "Knowledge Basis" not in response.text
    assert "参考知识来源（1 篇）" in response.text


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


def test_questionnaire_draft_form_reports_missing_selected_knowledge(
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

        latest_page = client.get(response.headers["location"])

    assert latest_page.status_code == 200
    assert "项目尚未选择任何知识文档" in latest_page.text


def test_questionnaire_draft_form_reports_no_design_knowledge_hits(
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
        replace_project_knowledge_selection(
            workspace_root=tmp_path,
            project_slug="analysis-only",
            knowledge_document_ids=[1],
        )

        response = client.post(
            "/projects/analysis-only/questionnaires/draft-form",
            data={"research_goal": "Evaluate monetization sentiment"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        latest_page = client.get(response.headers["location"])

    assert latest_page.status_code == 200
    assert "已选知识中没有命中当前问卷任务所需的内容" in latest_page.text


def test_questionnaire_history_uses_workspace_table(client, project_slug):
    client.post(
        f"/projects/{project_slug}/questionnaires/draft",
        json={"research_goal": "Player satisfaction"},
    )

    response = client.get(f"/projects/{project_slug}/questionnaires/history")

    assert response.status_code == 200
    html = response.text
    assert 'class="workspace-panel questionnaire-history-panel"' in html
    assert 'class="data-table questionnaire-history-table"' in html
