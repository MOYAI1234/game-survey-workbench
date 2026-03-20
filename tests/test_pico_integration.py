from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    with TestClient(create_app()) as test_client:
        yield test_client


def test_layout_includes_pico_css(client: TestClient):
    response = client.get("/")
    html = response.text
    assert "pico" in html.lower()
    assert "cdn.jsdelivr.net" in html or "pico.min.css" in html


def test_main_has_container_class(client: TestClient):
    response = client.get("/")
    html = response.text
    assert 'class="container' in html


def test_html_has_data_theme(client: TestClient):
    response = client.get("/")
    html = response.text
    assert 'data-theme="light"' in html


def test_app_css_defines_pico_primary(client: TestClient):
    response = client.get("/static/app.css")
    css = response.text
    assert "--pico-primary" in css


def test_project_settings_form_renders_with_pico(client: TestClient):
    client.post("/projects", json={"slug": "pico-test", "name": "Pico Test"})
    response = client.get("/projects/pico-test")
    assert response.status_code == 200
    html = response.text
    assert '<select name="language"' in html
    assert "保存设置" in html


def test_knowledge_page_renders_with_pico(client: TestClient):
    response = client.get("/knowledge")
    assert response.status_code == 200
    html = response.text
    assert '<select id="stage"' in html
    assert "共享知识库" in html


def test_analysis_page_renders_with_pico(client: TestClient):
    client.post("/projects", json={"slug": "ana-pico", "name": "Analysis Pico"})
    response = client.get("/projects/ana-pico/analysis/latest")
    assert response.status_code == 200


def test_brand_name_is_aurora_survey(client: TestClient):
    response = client.get("/")
    html = response.text
    assert "极光问卷" in html
    assert "游戏问卷研究工作台" not in html


def test_app_css_has_spinner_animation(client: TestClient):
    response = client.get("/static/app.css")
    css = response.text
    assert "@keyframes" in css
    assert "spinner" in css.lower()


def test_layout_includes_spinner_script(client: TestClient):
    response = client.get("/")
    html = response.text
    assert "data-loading-text" in html or "aurora-loading" in html or "<script>" in html


def test_script_handles_loading_attribute(client: TestClient):
    response = client.get("/")
    html = response.text
    assert "data-loading-text" in html
