from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from game_survey_workbench.app import create_app
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.dataset import DatasetRecord
from game_survey_workbench.services.dataset_import import import_dataset
from game_survey_workbench.services.reporting import render_report_markdown
from game_survey_workbench.services.workspace import bootstrap_workspace


def test_render_report_markdown_includes_required_sections():
    markdown = render_report_markdown(
        title="Version Satisfaction Report",
        summary_points=["Combat satisfaction is declining."],
        sections={"Key Findings": ["Top box fell among long-term payers."]},
    )

    assert "# Version Satisfaction Report" in markdown
    assert "## Key Findings" in markdown
    assert "Combat satisfaction is declining." in markdown


def test_generate_report_rejects_unknown_analysis_run_id(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    client = TestClient(create_app())
    client.post("/projects", json={"slug": "demo", "name": "Demo", "knowledge_pack": {}})

    response = client.post(
        "/projects/demo/reports/generate",
        json={"analysis_run_id": "missing-run"},
    )

    assert response.status_code == 404


def test_save_report_creates_unique_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    bootstrap_workspace(tmp_path)
    project_slug = "demo"
    dataset_path = tmp_path / "survey.csv"
    dataset_path.write_text(
        "Q1,Q2\nsingle_choice,scale\n满意,5\n",
        encoding="utf-8",
    )
    imported = import_dataset(dataset_path, project_slug=project_slug, workspace_root=tmp_path)

    client = TestClient(create_app())
    client.post("/projects", json={"slug": "demo", "name": "Demo", "knowledge_pack": {}})
    first = client.post(
        f"/projects/{project_slug}/reports/generate",
        json={"analysis_run_id": imported.analysis_run_id},
    )
    second = client.post(
        f"/projects/{project_slug}/reports/generate",
        json={"analysis_run_id": imported.analysis_run_id},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["path"] != second.json()["path"]


def test_generate_report_uses_analysis_run_record_for_project_validation(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    bootstrap_workspace(tmp_path)
    dataset_path = tmp_path / "survey.csv"
    dataset_path.write_text(
        "Q1,Q2\nsingle_choice,scale\n满意,5\n",
        encoding="utf-8",
    )
    imported = import_dataset(dataset_path, project_slug="project-a", workspace_root=tmp_path)

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        record = session.exec(
            select(DatasetRecord).where(DatasetRecord.dataset_id == imported.dataset_id)
        ).one()
        record.project_slug = "project-b"
        session.add(record)
        session.commit()

    client = TestClient(create_app())
    client.post("/projects", json={"slug": "project-a", "name": "Project A", "knowledge_pack": {}})
    client.post("/projects", json={"slug": "project-b", "name": "Project B", "knowledge_pack": {}})

    response = client.post(
        "/projects/project-b/reports/generate",
        json={"analysis_run_id": imported.analysis_run_id},
    )

    assert response.status_code == 404
