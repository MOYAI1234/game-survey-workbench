"""Report versioning and comparison."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.reporting import ReportRecord
from game_survey_workbench.services.report_versions import (
    diff_report_content,
    list_report_versions,
)


def test_list_report_versions_returns_most_recent_first(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        for i in range(3):
            session.add(
                ReportRecord(
                    project_slug="proj-a",
                    analysis_run_id=f"run-{i}",
                    path=f"/reports/v{i}.md",
                    created_at=datetime(2026, 3, 15, i, 0, 0, tzinfo=timezone.utc),
                )
            )
        session.commit()

        versions = list_report_versions(session, "proj-a")

    assert len(versions) == 3
    assert versions[0].path == "/reports/v2.md"


def test_diff_report_content_shows_changes():
    report_a = "# Report\n\n## Findings\n- Satisfaction: 4.1\n"
    report_b = "# Report\n\n## Findings\n- Satisfaction: 4.3\n- New finding\n"

    diff = diff_report_content(report_a, report_b, "v1", "v2")

    assert diff.added_lines >= 1
    assert "4.3" in diff.unified_diff


def test_report_history_page_lists_versions(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        session.add(
            ReportRecord(
                project_slug="proj-c",
                analysis_run_id="run-1",
                path="/reports/report-v1.md",
            )
        )
        session.add(
            ReportRecord(
                project_slug="proj-c",
                analysis_run_id="run-2",
                path="/reports/report-v2.md",
            )
        )
        session.commit()

    with TestClient(create_app()) as client:
        response = client.get("/projects/proj-c/reports/history")

    assert response.status_code == 200
    assert "Report History" in response.text
    assert "run-1" in response.text
    assert "run-2" in response.text
