import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    return TestClient(app)


def test_layout_has_nav(client):
    response = client.get("/")

    html = response.text
    assert "<nav" in html
    assert 'href="/"' in html


def test_all_pages_inherit_layout(client):
    slug = "nav-test"
    client.post("/projects", json={"slug": slug, "name": "Nav Test"})

    for path in [
        f"/projects/{slug}",
        f"/projects/{slug}/questionnaires/latest",
        f"/projects/{slug}/analysis/latest",
        f"/projects/{slug}/reports/latest",
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert "<nav" in response.text, f"Missing nav on {path}"
