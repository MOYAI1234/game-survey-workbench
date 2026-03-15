from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def project_slug(client):
    slug = "upload-test"
    client.post("/projects", json={"slug": slug, "name": "Upload Test"})
    return slug


def test_project_page_has_knowledge_upload_form(client, project_slug):
    response = client.get(f"/projects/{project_slug}")

    html = response.text
    assert 'enctype="multipart/form-data"' in html
    assert "knowledge" in html.lower()
    assert f'/projects/{project_slug}/knowledge/upload' in html


def test_project_page_has_dataset_upload_form(client, project_slug):
    response = client.get(f"/projects/{project_slug}")

    html = response.text
    assert f'/projects/{project_slug}/datasets/import-form' in html
    assert 'type="file"' in html


def test_knowledge_upload_stores_file(client, project_slug, tmp_path):
    md_content = b"---\ntitle: Test Doc\n---\n# Test Knowledge\nSome content."
    response = client.post(
        f"/projects/{project_slug}/knowledge/upload",
        files={"file": ("test-doc.md", md_content, "text/markdown")},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    assert (tmp_path / "knowledge" / "test-doc.md").exists()


def test_dataset_upload_via_form_redirects(client, project_slug):
    csv_content = (
        b"Q1_Satisfaction,Q2_Feedback\n"
        b"scale,free_text\n"
        b"5,Great game\n"
        b"3,Needs work\n"
    )
    response = client.post(
        f"/projects/{project_slug}/datasets/import-form",
        files={"file": ("survey.csv", csv_content, "text/csv")},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
