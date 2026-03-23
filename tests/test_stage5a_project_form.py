import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.services.research_waves import get_current_research_wave


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


def test_create_wave_form_redirects_to_wave_workspace(client):
    client.post("/projects", json={"slug": "demo", "name": "Demo"})

    response = client.post(
        "/projects/demo/waves/create",
        data={"name": "商业化专项", "goal_summary": "验证 1.1 版本商业化体验"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("/projects/demo/waves/1")


def test_switch_current_wave_marks_selected_wave_as_current(client, tmp_path):
    client.post("/projects", json={"slug": "demo", "name": "Demo"})
    client.post(
        "/projects/demo/waves/create",
        data={"name": "1.0 版本问卷", "goal_summary": ""},
        follow_redirects=False,
    )
    client.post(
        "/projects/demo/waves/create",
        data={"name": "1.1 版本问卷", "goal_summary": ""},
        follow_redirects=False,
    )

    response = client.post(
        "/projects/demo/waves/1/activate",
        follow_redirects=False,
    )

    current_wave = get_current_research_wave(
        workspace_root=tmp_path,
        project_slug="demo",
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("/projects/demo")
    assert current_wave is not None
    assert current_wave.id == 1
