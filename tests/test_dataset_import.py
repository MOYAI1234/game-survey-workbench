from pathlib import Path

from game_survey_workbench.services.dataset_import import import_dataset


def test_import_dataset_identifies_other_text_columns(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "Q1,Q1_其他说明,Q2\n满意,节奏太慢,5\n",
        encoding="utf-8",
    )

    dataset = import_dataset(csv_path, project_slug="version-feedback", workspace_root=tmp_path)

    assert dataset.question_columns["Q1"].other_text_column == "Q1_其他说明"
    assert dataset.question_columns["Q2"].question_type == "scale"
