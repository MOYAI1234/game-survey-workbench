from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.research_waves import create_research_wave


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
    create_research_wave(
        workspace_root=tmp_path,
        project_slug="bp",
        name="1.1 版本问卷",
        goal_summary="验证赛季通行证新版体验",
    )

    response = client.get("/projects/bp")

    assert response.status_code == 200
    html = response.text
    assert "Battle Pass" in html
    assert "Pass study" in html
    assert "Research Brief" in html or "研究简报" in html
    assert "研究轮次工作台" in html
    assert "1.1 版本问卷" in html
    assert "验证赛季通行证新版体验" in html
    assert "新建一轮研究" in html
    assert "任务计划" not in html
    assert "上传问卷数据" not in html
    assert "项目知识选择" in html
    assert "问卷设计" in html
    assert "数据分析" in html
    assert "报告生成" in html


def test_project_page_shows_wave_progress_instead_of_task_plan_placeholder(
    client: TestClient,
    tmp_path: Path,
):
    create_project(
        ProjectCreate(slug="progress-proj", name="Progress Project"),
        workspace_root=tmp_path,
    )
    create_research_wave(
        workspace_root=tmp_path,
        project_slug="progress-proj",
        name="1.1 版本问卷",
    )

    response = client.get("/projects/progress-proj")

    assert response.status_code == 200
    assert "当前轮次进度" in response.text
    assert "任务计划" not in response.text
    assert "当前版本不会自动生成任务计划" not in response.text
