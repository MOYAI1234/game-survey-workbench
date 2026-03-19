import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
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


def test_analysis_page_shows_used_knowledge_snippets_for_insight_basis(client, tmp_path):
    slug = "dash-knowledge"
    client.post("/projects", json={"slug": slug, "name": "Dashboard Knowledge"})
    source = tmp_path / "analysis-guide.md"
    source.write_text(
        "---\n"
        "title: Analysis Guide\n"
        "doc_type: guide\n"
        "stage:\n"
        "  - analysis\n"
        "---\n"
        "Use coded themes together with deterministic findings.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug=slug,
        knowledge_document_ids=[1],
    )

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
    run_id = response.json()["analysis_run_id"]

    code_response = client.post(
        f"/projects/{slug}/analysis/{run_id}/code-text",
        json={"question_column": "Q3_Feedback"},
    )
    assert code_response.status_code == 201

    insight_response = client.post(
        f"/projects/{slug}/analysis/{run_id}/insights",
        json={"research_goal": "Understand feedback drivers"},
    )
    assert insight_response.status_code == 201

    page = client.get(f"/projects/{slug}/analysis/{run_id}")

    assert page.status_code == 200
    html = page.text
    assert "Analysis Guide" in html
    assert "方法论池" in html
