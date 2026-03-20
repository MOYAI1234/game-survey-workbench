from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion
from game_survey_workbench.models.reporting import ReportRecord
from game_survey_workbench.services.workspace import bootstrap_workspace


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    report_dir = tmp_path / "projects" / "demo" / "reports"
    report_dir.mkdir(parents=True)
    report_path = report_dir / "report-test.md"
    report_path.write_text("# Report\n\n## Summary\n\nDone.", encoding="utf-8")

    with Session(engine) as session:
        session.add(ProjectRecord(slug="demo", name="Demo"))
        session.add(
            QuestionnaireSpecVersion(
                project_slug="demo",
                version_id="v1",
                research_goal="Goal",
                markdown_spec="## Q1\n\n- Question",
            )
        )
        session.add(
            ReportRecord(
                project_slug="demo",
                analysis_run_id="run-1",
                path=str(report_path),
            )
        )
        session.commit()
    return tmp_path


@pytest.fixture()
def app_client(workspace, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as client:
        yield client


def test_questionnaire_page_shows_download_links(app_client):
    response = app_client.get("/projects/demo/questionnaires/latest")
    html = response.text
    assert "download" in html.lower()
    assert "fmt=md" in html
    assert "fmt=txt" in html


def test_report_page_shows_download_links(app_client):
    response = app_client.get("/projects/demo/reports/latest")
    html = response.text
    assert "download" in html.lower()
    assert "fmt=md" in html
    assert "fmt=txt" in html
