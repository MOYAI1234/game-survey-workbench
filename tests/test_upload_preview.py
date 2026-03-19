from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.workspace import bootstrap_workspace


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)
    return tmp_path


@pytest.fixture()
def app_client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as c:
        yield c


def _make_single_header_csv(workspace: Path) -> Path:
    csv = workspace / "test_upload.csv"
    csv.write_text(
        "Gender,Feedback,Rating\n"
        "Male,Great game,5\n"
        "Female,Needs improvement,3\n"
        "Male,Love the graphics,4\n",
        encoding="utf-8",
    )
    return csv


def test_upload_preview_returns_preview_page_for_single_header(app_client, workspace):
    csv = _make_single_header_csv(workspace)
    with open(csv, "rb") as file_handle:
        response = app_client.post(
            "/projects/demo/datasets/upload-preview",
            files={"file": ("test.csv", file_handle, "text/csv")},
        )

    assert response.status_code == 200
    html = response.text
    assert "预览" in html or "Preview" in html
    assert "Gender" in html
    assert "Feedback" in html


def test_upload_preview_returns_preview_page_for_dual_header(app_client, workspace):
    csv = workspace / "dual.csv"
    csv.write_text(
        "Gender,Feedback,Rating\n"
        "single_choice,free_text,scale\n"
        "Male,Great,5\n",
        encoding="utf-8",
    )

    with open(csv, "rb") as file_handle:
        response = app_client.post(
            "/projects/demo/datasets/upload-preview",
            files={"file": ("dual.csv", file_handle, "text/csv")},
        )

    assert response.status_code == 200
    assert "Gender" in response.text


def test_confirm_import_creates_dataset_and_redirects(app_client, workspace):
    csv = _make_single_header_csv(workspace)
    with open(csv, "rb") as file_handle:
        preview_resp = app_client.post(
            "/projects/demo/datasets/upload-preview",
            files={"file": ("test.csv", file_handle, "text/csv")},
        )

    assert preview_resp.status_code == 200

    staging_dir = workspace / "projects" / "demo" / "data" / "staging"
    staging_files = list(staging_dir.glob("*.csv"))
    assert len(staging_files) == 1
    staging_id = staging_files[0].stem

    response = app_client.post(
        "/projects/demo/datasets/confirm-import",
        data={
            "staging_id": staging_id,
            "column_types": ["single_choice", "free_text", "scale"],
            "column_include": ["Gender", "Feedback", "Rating"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "/analysis/" in response.headers["location"]
    assert not staging_files[0].exists()


def test_upload_preview_rejects_unreadable_file(app_client, workspace):
    bad = workspace / "bad.bin"
    bad.write_bytes(b"\x00\x01\x02")

    with open(bad, "rb") as file_handle:
        response = app_client.post(
            "/projects/demo/datasets/upload-preview",
            files={"file": ("bad.bin", file_handle, "application/octet-stream")},
        )

    assert response.status_code in (400, 303)
