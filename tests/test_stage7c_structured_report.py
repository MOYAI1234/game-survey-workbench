"""End-to-end structured report generation."""

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


def _setup_project_with_brief_and_dataset(client: TestClient, tmp_path: Path) -> str:
    client.post("/projects", json={"slug": "rpt-test", "name": "Report Test"})

    client.put(
        "/projects/rpt-test/brief",
        json={
            "background": "Mobile game satisfaction study Q1 2026",
            "objectives": [
                "Measure overall satisfaction",
                "Identify churn risk factors",
            ],
            "target_audience": "Players with 14+ days tenure",
            "hypotheses": ["Spenders are more satisfied than non-spenders"],
            "success_criteria": "",
        },
    )

    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "satisfaction,feedback\n"
        "scale,free_text\n"
        "5,great game love it\n"
        "3,too many ads\n"
        "4,good but expensive\n"
        "2,boring after a week\n",
        encoding="utf-8",
    )
    with csv_path.open("rb") as handle:
        response = client.post(
            "/projects/rpt-test/datasets/import",
            files={"file": ("survey.csv", handle, "text/csv")},
        )

    return response.json()["analysis_run_id"]


def test_structured_report_uses_business_report_sections(client: TestClient, tmp_path: Path):
    run_id = _setup_project_with_brief_and_dataset(client, tmp_path)

    response = client.post(
        "/projects/rpt-test/reports/generate",
        json={"analysis_run_id": run_id},
    )

    report_path = Path(response.json()["path"])
    content = report_path.read_text(encoding="utf-8")

    assert "## 一页摘要" in content
    assert "## 核心洞察" in content
    assert "## 关键图表说明" in content
    assert "## 建议动作" in content
    assert "## 参考来源" in content
    assert "## 研究方法" not in content
    assert "## 统计发现" not in content
    assert "## 定性主题" not in content


def test_structured_report_includes_brief_context(client: TestClient, tmp_path: Path):
    run_id = _setup_project_with_brief_and_dataset(client, tmp_path)

    response = client.post(
        "/projects/rpt-test/reports/generate",
        json={"analysis_run_id": run_id},
    )

    report_path = Path(response.json()["path"])
    content = report_path.read_text(encoding="utf-8")

    assert "satisfaction study" in content.lower() or "churn risk" in content.lower()
    assert "## 核心洞察" in content
