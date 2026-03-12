from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.services.dataset_import import (
    detect_question_type_from_header_and_series,
    import_dataset,
)


def test_import_dataset_identifies_other_text_columns(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "Q1,Q1_其他说明,Q2\nsingle_choice,free_text,scale\n满意,节奏太慢,5\n",
        encoding="utf-8",
    )

    dataset = import_dataset(csv_path, project_slug="version-feedback", workspace_root=tmp_path)

    assert dataset.question_columns["Q1"].other_text_column == "Q1_其他说明"
    assert dataset.question_columns["Q2"].question_type == "scale"


def test_import_dataset_route_accepts_uploaded_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    client = TestClient(create_app())
    client.post("/projects", json={"slug": "upload-demo", "name": "Upload Demo", "knowledge_pack": {}})

    response = client.post(
        "/projects/upload-demo/datasets/import",
        files={
            "file": (
                "survey.csv",
                "Q1,Q1_其他说明,Q2\nsingle_choice,free_text,scale\n满意,节奏太慢,5\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["project_slug"] == "upload-demo"
    assert payload["question_columns"]["Q1"]["other_text_column"] == "Q1_其他说明"


def test_detect_question_type_marks_multiple_choices_question_as_multi_select():
    result = detect_question_type_from_header_and_series(
        "What are your most satisfying parts? (Multiple Choices)",
        pd.Series(["Reward A;Reward B", "Reward C"]),
    )

    assert result == "multi_select"


def test_detect_question_type_marks_free_text_prompt_as_free_text():
    result = detect_question_type_from_header_and_series(
        "Feel free to tell us your suggestion",
        pd.Series(["More rewards please", "It feels expensive"]),
    )

    assert result == "free_text"


def test_detect_question_type_does_not_treat_comma_delimited_free_text_as_multi_select():
    result = detect_question_type_from_header_and_series(
        "What do you think about the current pass rewards?",
        pd.Series(
            [
                "Too expensive, especially for new players",
                "Rewards feel repetitive, and the pacing is slow",
            ]
        ),
    )

    assert result == "free_text"


def test_import_dataset_uses_second_header_row_as_type_source_of_truth(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "分层,Q1,Q2\n"
        "metadata,multi_select,free_text\n"
        "免费玩家,Reward A;Reward B,希望奖励更多\n",
        encoding="utf-8",
    )

    dataset = import_dataset(csv_path, project_slug="demo", workspace_root=tmp_path)

    assert "分层" not in dataset.question_columns
    assert dataset.question_columns["Q1"].question_type == "multi_select"
    assert dataset.question_columns["Q2"].question_type == "free_text"


def test_import_dataset_excludes_metadata_columns_from_question_schema(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "标记,时间戳记,Q1\nmetadata,metadata,single_choice\n1,2026-03-12 10:00,满意\n",
        encoding="utf-8",
    )

    dataset = import_dataset(csv_path, project_slug="demo", workspace_root=tmp_path)

    assert "标记" not in dataset.question_columns
    assert "时间戳记" not in dataset.question_columns
