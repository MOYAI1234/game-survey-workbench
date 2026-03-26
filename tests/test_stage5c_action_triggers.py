import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def project_with_analysis(client, tmp_path):
    slug = "trigger-test"
    client.post("/projects", json={"slug": slug, "name": "Trigger Test"})

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    (knowledge_dir / "guide.md").write_text(
        "---\ntitle: Research Guide\ndoc_type: guide\nstages:\n  - analysis\nscenario: trigger-test\npriority: 1\n---\n# Guide\nPlayer satisfaction research guidance.",
        encoding="utf-8",
    )

    csv_content = (
        "Q1_Score,Q2_Feedback\n"
        "scale,free_text\n"
        "5,Love the graphics\n"
        "3,Too many ads\n"
        "4,Good gameplay\n"
        "2,Crashes often\n"
    )
    response = client.post(
        f"/projects/{slug}/datasets/import",
        files={"file": ("data.csv", csv_content.encode(), "text/csv")},
    )
    run_id = response.json()["analysis_run_id"]
    return slug, run_id


def test_code_text_all_route_exists(client, project_with_analysis):
    slug, run_id = project_with_analysis

    response = client.post(
        f"/projects/{slug}/analysis/{run_id}/code-text-all",
        follow_redirects=False,
    )

    assert response.status_code in (201, 302, 303)


def test_insights_generate_form_route_exists(client, project_with_analysis):
    slug, run_id = project_with_analysis
    client.post(f"/projects/{slug}/analysis/{run_id}/code-text-all")

    response = client.post(
        f"/projects/{slug}/analysis/{run_id}/insights-generate",
        data={"research_goal": "Understand player satisfaction"},
        follow_redirects=False,
    )

    assert response.status_code in (201, 302, 303)


def test_latest_code_text_all_route_uses_latest_analysis_run(client, project_with_analysis):
    slug, _run_id = project_with_analysis

    response = client.post(
        f"/projects/{slug}/analysis/latest/code-text-all",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/projects/{slug}/analysis/latest"


def test_latest_insights_route_uses_latest_analysis_run(client, project_with_analysis):
    slug, run_id = project_with_analysis
    client.post(f"/projects/{slug}/analysis/{run_id}/code-text-all")

    response = client.post(
        f"/projects/{slug}/analysis/latest/insights-generate",
        data={"research_goal": "Understand player satisfaction"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/projects/{slug}/analysis/latest"


def test_analysis_detail_shows_text_coding_status_shell(client, project_with_analysis):
    slug, run_id = project_with_analysis

    response = client.get(f"/projects/{slug}/analysis/{run_id}")

    assert response.status_code == 200
    assert 'data-coding-status-url=' in response.text
    assert 'coding-progress-shell' in response.text
