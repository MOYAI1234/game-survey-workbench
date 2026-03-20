from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    create_project(
        ProjectCreate(slug="demo", name="Demo", language="zh"),
        workspace_root=tmp_path,
    )
    return tmp_path


@pytest.fixture()
def app_client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as client:
        yield client


def test_report_generation_passes_project_language_to_report_builder(
    workspace: Path,
    app_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from game_survey_workbench.routes import reports as reports_route

    captured: dict[str, str] = {}

    monkeypatch.setattr(
        reports_route,
        "get_analysis_run_record",
        lambda **kwargs: SimpleNamespace(project_slug="demo"),
    )
    monkeypatch.setattr(
        reports_route,
        "get_coding_results",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        reports_route,
        "get_latest_insight_record",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        reports_route,
        "get_research_brief",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        reports_route,
        "build_deterministic_findings_for_run",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        reports_route,
        "load_analysis_run_context",
        lambda **kwargs: SimpleNamespace(
            dataset_record=SimpleNamespace(dataset_schema={}),
            dataframe=pd.DataFrame(),
        ),
    )
    monkeypatch.setattr(
        reports_route,
        "generate_structured_report",
        lambda **kwargs: captured.setdefault("language", kwargs.get("language")) or "# Report",
    )
    monkeypatch.setattr(
        reports_route,
        "save_report",
        lambda **kwargs: workspace / "projects" / "demo" / "reports" / "report.md",
    )
    monkeypatch.setattr(
        reports_route,
        "record_workflow_event",
        lambda **kwargs: None,
    )

    response = app_client.post(
        "/projects/demo/reports/generate",
        json={"analysis_run_id": "run-1"},
    )

    assert response.status_code == 201
    assert captured["language"] == "zh"
