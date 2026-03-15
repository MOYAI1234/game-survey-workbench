"""Analysis dashboard shows workflow progress."""

from pathlib import Path

from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


def test_analysis_page_shows_step_checklist(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))

    with TestClient(create_app()) as client:
        client.post("/projects", json={"slug": "prog-proj", "name": "Progress"})
        response = client.post(
            "/projects/prog-proj/datasets/import",
            files={
                "file": (
                    "data.csv",
                    ("Q1\nsingle_choice\nA\nB\n").encode(),
                    "text/csv",
                )
            },
        )
        run_id = response.json()["analysis_run_id"]

        analysis_response = client.get(f"/projects/prog-proj/analysis/{run_id}")

    assert analysis_response.status_code == 200
    content = analysis_response.text.lower()
    assert "research progress" in content
    assert "dataset imported" in content or "imported" in content
