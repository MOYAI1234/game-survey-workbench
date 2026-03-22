from pathlib import Path

from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.models.analysis_run import get_analysis_run
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.research_waves import create_research_wave
from game_survey_workbench.services.dataset_import import import_dataset


def test_import_dataset_creates_analysis_run_record(tmp_path: Path):
    create_project(
        ProjectCreate(slug="demo", name="Demo"),
        workspace_root=tmp_path,
    )
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "Q1,Q2\nsingle_choice,scale\n满意,5\n",
        encoding="utf-8",
    )

    dataset = import_dataset(csv_path, project_slug="demo", workspace_root=tmp_path)

    run = get_analysis_run(dataset.analysis_run_id, workspace_root=tmp_path)

    assert run.project_slug == "demo"
    assert run.dataset_id == dataset.dataset_id


def test_import_dataset_creates_analysis_run_record_for_current_wave(tmp_path: Path):
    create_project(
        ProjectCreate(slug="demo", name="Demo"),
        workspace_root=tmp_path,
    )
    wave = create_research_wave(
        workspace_root=tmp_path,
        project_slug="demo",
        name="1.1 版本问卷",
    )
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "Q1,Q2\nsingle_choice,scale\n满意,5\n",
        encoding="utf-8",
    )

    dataset = import_dataset(csv_path, project_slug="demo", workspace_root=tmp_path)

    run = get_analysis_run(dataset.analysis_run_id, workspace_root=tmp_path)

    assert run.wave_id == wave.id


def test_dataset_upload_belongs_to_wave_analysis_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    client = TestClient(create_app())
    client.post("/projects", json={"slug": "demo", "name": "Demo"})
    wave = create_research_wave(
        workspace_root=tmp_path,
        project_slug="demo",
        name="1.1 版本问卷",
    )

    response = client.get(f"/projects/demo/waves/{wave.id}/analysis")

    assert "上传问卷数据" in response.text
    assert "导入数据" in response.text
