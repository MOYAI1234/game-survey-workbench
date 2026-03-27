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


def test_project_sidebar_shows_on_project_detail(client: TestClient):
    client.post("/projects", json={"slug": "nav-test", "name": "Nav Test"})
    response = client.get("/projects/nav-test")
    html = response.text
    assert 'class="project-sidebar"' in html
    assert 'class="workspace-shell"' in html
    assert 'href="/projects/nav-test"' in html
    assert 'href="/projects/nav-test/questionnaires/latest"' in html
    assert 'href="/projects/nav-test/analysis/latest"' in html
    assert 'href="/projects/nav-test/reports/latest"' in html


def test_project_sidebar_shows_on_questionnaire_page(client: TestClient):
    client.post("/projects", json={"slug": "nav-test2", "name": "Nav Test2"})
    response = client.get("/projects/nav-test2/questionnaires/latest")
    html = response.text
    assert 'class="project-sidebar"' in html
    assert 'class="workspace-shell"' in html
    assert 'href="/projects/nav-test2/questionnaires/latest"' in html


def test_project_sidebar_absent_on_homepage(client: TestClient):
    response = client.get("/")
    html = response.text
    assert 'class="project-sidebar"' not in html


def test_project_sidebar_absent_on_knowledge_page(client: TestClient):
    response = client.get("/knowledge")
    html = response.text
    assert 'class="project-sidebar"' not in html


def test_project_settings_appear_before_wave_workspace(client: TestClient):
    client.post("/projects", json={"slug": "order-test", "name": "Order Test"})
    response = client.get("/projects/order-test")
    html = response.text
    workflow_pos = html.find("研究轮次工作台")
    settings_pos = html.find("项目设置")
    assert workflow_pos != -1
    assert settings_pos != -1
    assert settings_pos < workflow_pos


def test_project_context_appears_before_wave_workspace(client: TestClient):
    client.post("/projects", json={"slug": "order-test2", "name": "Order Test2"})
    response = client.get("/projects/order-test2")
    html = response.text
    brief_pos = html.find("研究简报")
    knowledge_pos = html.find("项目知识选择")
    wave_pos = html.find("研究轮次工作台")
    assert brief_pos != -1
    assert knowledge_pos != -1
    assert wave_pos != -1
    assert brief_pos < wave_pos
    assert knowledge_pos < wave_pos


def test_project_page_no_longer_shows_data_upload_form(client: TestClient):
    client.post("/projects", json={"slug": "order-test2b", "name": "Order Test2B"})
    response = client.get("/projects/order-test2b")
    html = response.text
    upload_pos = html.find("上传问卷数据")
    brief_pos = html.find("研究简报")
    assert upload_pos == -1
    assert brief_pos != -1


def test_project_config_in_details_element(client: TestClient):
    client.post("/projects", json={"slug": "order-test3", "name": "Order Test3"})
    response = client.get("/projects/order-test3")
    html = response.text
    assert "项目配置" in html
    details_pos = html.find("<details")
    config_pos = html.find("项目配置")
    assert details_pos != -1
    assert details_pos < config_pos


def test_homepage_no_workflow_overview_section(client: TestClient):
    response = client.get("/")
    html = response.text
    assert 'class="workflow-overview"' not in html


def test_homepage_uses_project_card_grid(client: TestClient):
    client.post("/projects", json={"slug": "grid-test", "name": "Grid Test"})
    response = client.get("/")
    html = response.text
    assert 'class="project-card-grid"' in html
    assert 'class="project-card"' in html
    assert "Grid Test" in html


def test_homepage_wraps_knowledge_summary_in_details(client: TestClient):
    response = client.get("/")
    html = response.text
    assert 'class="knowledge-summary-panel"' in html
    assert "<details" in html


def test_alert_success_uses_no_hardcoded_green(client: TestClient):
    response = client.get("/static/app.css")
    css = response.text
    assert "#f0fdf4" not in css
    assert "#86efac" not in css
    assert "#166534" not in css


def test_step_hint_uses_brand_color(client: TestClient):
    response = client.get("/static/app.css")
    css = response.text
    assert "#2563eb" not in css


def test_step_done_uses_warm_color(client: TestClient):
    response = client.get("/static/app.css")
    css = response.text
    assert "#2f6b2f" not in css


def test_app_css_has_prose_class(client: TestClient):
    response = client.get("/static/app.css")
    css = response.text
    assert ".prose" in css


def test_app_css_has_project_sidebar(client: TestClient):
    response = client.get("/static/app.css")
    css = response.text
    assert ".project-sidebar" in css
    assert ".project-card-grid" in css
    assert ".inline-status-note" in css
    assert ".confirm-dialog-shell" in css


def test_layout_includes_confirm_dialog_shell(client: TestClient):
    response = client.get("/")
    html = response.text
    assert 'id="confirm-dialog-shell"' in html
    assert 'id="confirm-dialog-confirm"' in html


def test_app_css_has_sidebar_toggle_classes(client: TestClient):
    response = client.get("/static/app.css")
    css = response.text
    assert ".split-workspace" in css
    assert ".workspace-inline-actions" in css
    assert ".status-summary-card" in css
    assert ".status-token" in css
