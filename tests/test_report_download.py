from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.models.reporting import ReportRecord
from game_survey_workbench.services.workspace import bootstrap_workspace

SAMPLE_REPORT = """\
# Demo Report

*Report generated 2026-03-19*

## Executive Summary

Key finding here.

## Methodology

**Sample:** 100 respondents
"""


@pytest.fixture()
def workspace_with_report(tmp_path: Path) -> tuple[Path, int]:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    report_dir = tmp_path / "projects" / "demo" / "reports"
    report_dir.mkdir(parents=True)
    report_path = report_dir / "report-test.md"
    report_path.write_text(SAMPLE_REPORT, encoding="utf-8")

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        session.add(ProjectRecord(slug="demo", name="Demo"))
        record = ReportRecord(
            project_slug="demo",
            analysis_run_id="run-1",
            path=str(report_path),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        report_id = record.id
    return tmp_path, report_id


@pytest.fixture()
def app_client(workspace_with_report, monkeypatch):
    workspace, _ = workspace_with_report
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as client:
        yield client


def test_download_report_latest_as_md(app_client):
    response = app_client.get("/projects/demo/reports/latest/download?fmt=md")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "## Executive Summary" in response.text
    assert "attachment" in response.headers.get("content-disposition", "")


def test_download_report_latest_as_txt(app_client):
    response = app_client.get("/projects/demo/reports/latest/download?fmt=txt")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "##" not in response.text
    assert "Executive Summary" in response.text


def test_download_report_by_id(app_client, workspace_with_report):
    _, report_id = workspace_with_report
    response = app_client.get(f"/projects/demo/reports/{report_id}/download")
    assert response.status_code == 200
    assert "Demo Report" in response.text


def test_download_report_returns_404_when_no_reports_exist(app_client):
    response = app_client.get("/projects/nonexistent/reports/latest/download")
    assert response.status_code == 404
