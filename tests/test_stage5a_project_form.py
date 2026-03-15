import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    return TestClient(app)


def test_landing_page_has_project_creation_form(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert "<form" in html
    assert 'action="/projects/create"' in html
    assert 'name="slug"' in html
    assert 'name="name"' in html


def test_create_project_via_form_redirects_to_project_page(client):
    response = client.post(
        "/projects/create",
        data={
            "slug": "test-project",
            "name": "Test Project",
            "description": "A test",
        },
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    assert "/projects/test-project" in response.headers["location"]


def test_created_project_appears_on_landing_page(client):
    client.post(
        "/projects/create",
        data={"slug": "my-proj", "name": "My Project", "description": ""},
        follow_redirects=False,
    )

    response = client.get("/")

    assert "My Project" in response.text
