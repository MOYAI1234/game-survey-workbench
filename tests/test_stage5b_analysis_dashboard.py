import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def project_with_dataset(client):
    slug = "dash-test"
    client.post("/projects", json={"slug": slug, "name": "Dashboard Test"})
    csv_content = (
        "Q1_Satisfaction,Q2_Genre,Q3_Feedback\n"
        "scale,single_choice,free_text\n"
        "5,RPG,Love it\n"
        "3,FPS,Needs work\n"
        "4,RPG,Pretty good\n"
    )
    response = client.post(
        f"/projects/{slug}/datasets/import",
        files={"file": ("survey.csv", csv_content.encode(), "text/csv")},
    )
    data = response.json()
    return slug, data["analysis_run_id"]


def test_analysis_page_shows_deterministic_findings(client, project_with_dataset):
    slug, run_id = project_with_dataset

    response = client.get(f"/projects/{slug}/analysis/{run_id}")

    assert response.status_code == 200
    html = response.text
    assert "Q1_Satisfaction" in html or "Satisfaction" in html
    assert "mean" in html.lower() or "average" in html.lower() or "top" in html.lower()


def test_analysis_page_shows_dataset_schema(client, project_with_dataset):
    slug, run_id = project_with_dataset

    response = client.get(f"/projects/{slug}/analysis/{run_id}")

    html = response.text
    assert "scale" in html
    assert "single_choice" in html or "single choice" in html.lower()
    assert "free_text" in html or "free text" in html.lower()


def test_analysis_page_without_run_id_shows_latest(client, project_with_dataset):
    slug, _ = project_with_dataset

    response = client.get(f"/projects/{slug}/analysis/latest")

    assert response.status_code == 200
