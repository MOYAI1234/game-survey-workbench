from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    with TestClient(create_app()) as test_client:
        yield test_client


def test_layout_nav_is_chinese(client: TestClient):
    response = client.get("/")

    assert response.status_code == 200
    assert "游戏问卷研究工作台" in response.text


def test_index_page_is_chinese(client: TestClient):
    response = client.get("/")
    content = response.text

    assert "新建项目" in content
    assert "项目标识" in content
    assert "项目名称" in content
    assert "POST /projects" not in content
    assert "Create New Project" not in content
    assert "Slug (URL identifier)" not in content


def test_index_empty_state_chinese(client: TestClient):
    response = client.get("/")

    assert "暂无项目" in response.text
    assert "POST /projects" not in response.text


def test_project_detail_is_chinese(client: TestClient):
    client.post("/projects", json={"slug": "test-cn", "name": "中文测试"})

    response = client.get("/projects/test-cn")
    content = response.text

    assert "研究简报" in content
    assert "研究背景" in content
    assert "研究目标" in content
    assert "上传知识文档" in content
    assert "上传问卷数据" in content
    assert "PUT /projects/" not in content
    assert "双层表头" in content


def test_knowledge_upload_has_feedback(client: TestClient, tmp_path: Path):
    client.post("/projects", json={"slug": "kb-test", "name": "KB Test"})
    md_file = tmp_path / "test_knowledge.md"
    md_file.write_text("# Test Knowledge\n\nSome content here.", encoding="utf-8")

    with md_file.open("rb") as handle:
        response = client.post(
            "/projects/kb-test/knowledge/upload",
            files={"file": ("test.md", handle, "text/markdown")},
            follow_redirects=False,
        )

    assert response.status_code == 303
    location = response.headers["location"]
    assert "upload_success=" in location or "success" in location.lower()
