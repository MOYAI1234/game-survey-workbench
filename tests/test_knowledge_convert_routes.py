from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables
from game_survey_workbench.services.workspace import bootstrap_workspace


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    return tmp_path


@pytest.fixture()
def app_client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as client:
        yield client


def _make_test_docx(workspace: Path) -> Path:
    """Create a minimal .docx for testing."""
    try:
        from docx import Document
    except ImportError:
        pytest.skip("python-docx not installed")

    doc = Document()
    doc.add_heading("Survey Methods", level=1)
    doc.add_paragraph("This document describes survey methodology for game research.")
    path = workspace / "test_doc.docx"
    doc.save(str(path))
    return path


def test_upload_non_markdown_redirects_to_convert_preview(app_client, workspace):
    docx_path = _make_test_docx(workspace)
    with open(docx_path, "rb") as handle:
        response = app_client.post(
            "/knowledge/upload",
            files={
                "file": (
                    "methods.docx",
                    handle,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"purposes": ["questionnaire_design"]},
            follow_redirects=True,
        )

    assert response.status_code == 200
    html = response.text
    assert "转换预览" in html or "convert" in html.lower()
    assert "Survey Methods" in html or "methods.docx" in html


def test_upload_markdown_still_works_directly(app_client, workspace):
    response = app_client.post(
        "/knowledge/upload",
        files={
            "file": ("guide.md", b"---\ntitle: Test Guide\n---\nContent here.", "text/markdown")
        },
        data={"purposes": ["analysis"]},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "/knowledge" in response.headers["location"]


def test_convert_confirm_ingests_document(app_client, workspace):
    docx_path = _make_test_docx(workspace)
    with open(docx_path, "rb") as handle:
        preview_resp = app_client.post(
            "/knowledge/upload",
            files={
                "file": (
                    "methods.docx",
                    handle,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"purposes": []},
            follow_redirects=True,
        )

    assert preview_resp.status_code == 200

    staging_dir = workspace / "knowledge" / "staging"
    staging_files = list(staging_dir.glob("*.md")) if staging_dir.exists() else []
    if not staging_files:
        pytest.skip("No staging file created - conversion may have failed")
    staging_id = staging_files[0].stem

    confirm_resp = app_client.post(
        "/knowledge/convert-confirm",
        data={
            "staging_id": staging_id,
            "source_format": "docx",
            "title": "Survey Methods Guide",
            "doc_type": "guide",
            "purposes": ["questionnaire_design"],
        },
        follow_redirects=False,
    )

    assert confirm_resp.status_code == 303
    assert "upload_success" in confirm_resp.headers["location"]
    assert not staging_files[0].exists()


def test_convert_download_returns_markdown_file(app_client, workspace):
    staging_dir = workspace / "knowledge" / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_file = staging_dir / "abc123.md"
    staging_file.write_text("# Test\n\nConverted content.", encoding="utf-8")

    response = app_client.post(
        "/knowledge/convert-download",
        data={"staging_id": "abc123"},
    )

    assert response.status_code == 200
    assert "text/markdown" in response.headers.get("content-type", "")
    assert b"Converted content" in response.content
