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


def test_project_homepage_shows_brief_section(client: TestClient, tmp_path: Path):
    create_project(
        ProjectCreate(slug="bp", name="Battle Pass", description="Pass study"),
        workspace_root=tmp_path,
    )

    response = client.get("/projects/bp")

    assert response.status_code == 200
    html = response.text
    assert "Battle Pass" in html
    assert "Pass study" in html
    assert "Research Brief" in html or "研究简报" in html
    assert "Task Plan" in html or "任务计划" in html
    assert "问卷设计" in html
    assert "数据分析" in html
    assert "报告生成" in html
