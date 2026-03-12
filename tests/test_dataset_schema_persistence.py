from pathlib import Path

from game_survey_workbench.services.dataset_import import import_dataset


def test_import_dataset_persists_column_role_and_analysis_flags(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text("Q1,Q1_其他说明\n满意,节奏太慢\n", encoding="utf-8")

    dataset = import_dataset(csv_path, project_slug="demo", workspace_root=tmp_path)

    assert dataset.question_columns["Q1"].column_role == "question"
    assert dataset.question_columns["Q1"].include_in_analysis is True
