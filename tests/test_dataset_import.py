from pathlib import Path

from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
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


def test_import_dataset_route_accepts_uploaded_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    client = TestClient(create_app())
    client.post("/projects", json={"slug": "upload-demo", "name": "Upload Demo", "knowledge_pack": {}})

    response = client.post(
        "/projects/upload-demo/datasets/import",
        files={"file": ("survey.csv", "Q1,Q1_其他说明,Q2\n满意,节奏太慢,5\n", "text/csv")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["project_slug"] == "upload-demo"
    assert payload["question_columns"]["Q1"]["other_text_column"] == "Q1_其他说明"
