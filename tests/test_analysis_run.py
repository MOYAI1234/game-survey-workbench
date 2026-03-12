from pathlib import Path

from game_survey_workbench.models.analysis_run import get_analysis_run
from game_survey_workbench.services.dataset_import import import_dataset


def test_import_dataset_creates_analysis_run_record(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "Q1,Q2\nsingle_choice,scale\n满意,5\n",
        encoding="utf-8",
    )

    dataset = import_dataset(csv_path, project_slug="demo", workspace_root=tmp_path)

    run = get_analysis_run(dataset.analysis_run_id, workspace_root=tmp_path)

    assert run.project_slug == "demo"
    assert run.dataset_id == dataset.dataset_id
