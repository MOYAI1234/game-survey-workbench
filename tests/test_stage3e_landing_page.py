from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    with TestClient(create_app()) as test_client:
        yield test_client


def test_landing_page_lists_projects(client: TestClient, tmp_path: Path):
    create_project(
        ProjectCreate(slug="alpha", name="Alpha Study"),
        workspace_root=tmp_path,
    )
    create_project(
        ProjectCreate(slug="beta", name="Beta Study"),
        workspace_root=tmp_path,
    )

    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert "Alpha Study" in html
    assert "Beta Study" in html
    assert "/projects/alpha" in html
    assert "/projects/beta" in html


def test_landing_page_empty_state(client: TestClient):
    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert "No projects yet" in html or "暂无项目" in html
