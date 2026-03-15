import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def project_slug(client):
    slug = "brief-test"
    client.post("/projects", json={"slug": slug, "name": "Brief Test"})
    return slug


def test_project_page_has_brief_form(client, project_slug):
    response = client.get(f"/projects/{project_slug}")

    html = response.text
    assert 'name="background"' in html
    assert 'name="objectives"' in html
    assert f'/projects/{project_slug}/brief/save' in html


def test_submit_brief_form_saves_and_redirects(client, project_slug):
    response = client.post(
        f"/projects/{project_slug}/brief/save",
        data={
            "background": "Testing player satisfaction in a mobile RPG",
            "objectives": "Measure NPS\nIdentify churn drivers",
            "hypotheses": "Whales are more satisfied",
            "target_audience": "Active players past 30 days",
            "success_criteria": "Response rate > 15%",
        },
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    brief_response = client.get(f"/projects/{project_slug}/brief")
    assert brief_response.status_code == 200
    data = brief_response.json()
    assert data["background"] == "Testing player satisfaction in a mobile RPG"
    assert "Measure NPS" in data["objectives"]


def test_project_page_shows_saved_brief(client, project_slug):
    client.put(
        f"/projects/{project_slug}/brief",
        json={
            "background": "RPG satisfaction study",
            "objectives": ["Measure NPS"],
            "hypotheses": [],
            "target_audience": "All players",
            "success_criteria": "",
        },
    )

    response = client.get(f"/projects/{project_slug}")

    assert "RPG satisfaction study" in response.text
