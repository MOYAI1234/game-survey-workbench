from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    with TestClient(create_app()) as test_client:
        yield test_client


def _ingest_markdown(tmp_path: Path, *, filename: str, content: str) -> None:
    source = tmp_path / filename
    source.write_text(content, encoding="utf-8")
    ingest_knowledge_file(source, project_root=tmp_path)


def test_homepage_shows_shared_knowledge_entry(
    client: TestClient,
    tmp_path: Path,
):
    _ingest_markdown(
        tmp_path,
        filename="knowledge-one.md",
        content=(
            "---\n"
            "title: 问卷设计参考\n"
            "doc_type: guide\n"
            "stage:\n"
            "  - design\n"
            "priority: 1\n"
            "---\n\n"
            "# 问卷设计参考\n\n这里是内容。"
        ),
    )

    response = client.get("/")

    assert response.status_code == 200
    content = response.text
    assert "共享知识库" in content
    assert "已入库知识文档" in content
    assert "问卷设计参考" in content
    assert "/knowledge" in content
