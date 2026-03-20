"""Report detail page shows structured content and history link."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    with TestClient(create_app()) as test_client:
        yield test_client


def test_report_page_has_history_link(client: TestClient, tmp_path: Path):
    client.post("/projects", json={"slug": "detail-proj", "name": "Detail"})

    csv_path = tmp_path / "data.csv"
    csv_path.write_text("Q1\nsingle_choice\nA\nB\n", encoding="utf-8")
    with csv_path.open("rb") as handle:
        response = client.post(
            "/projects/detail-proj/datasets/import",
            files={"file": ("data.csv", handle, "text/csv")},
        )

    run_id = response.json()["analysis_run_id"]
    client.post(
        "/projects/detail-proj/reports/generate",
        json={"analysis_run_id": run_id},
    )

    detail_response = client.get("/projects/detail-proj/reports/latest")

    assert detail_response.status_code == 200
    assert '/projects/detail-proj/reports/history' in detail_response.text
    assert "<pre" not in detail_response.text
    assert "<h2>研究方法</h2>" in detail_response.text
    assert "Question Types:" in detail_response.text
