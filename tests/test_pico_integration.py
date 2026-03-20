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
