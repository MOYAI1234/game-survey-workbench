from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from game_survey_workbench.app import create_app
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
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


def test_shared_knowledge_page_lists_documents_and_upload_form(
    client: TestClient,
    tmp_path: Path,
):
    _ingest_markdown(
        tmp_path,
        filename="knowledge-two.md",
        content=(
            "---\n"
            "title: 分析方法库\n"
            "doc_type: guide\n"
            "stage:\n"
            "  - analysis\n"
            "priority: 1\n"
            "---\n\n"
            "# 分析方法库\n\n这里是分析内容。"
        ),
    )

    response = client.get("/knowledge")

    assert response.status_code == 200
    content = response.text
    assert "共享知识库" in content
    assert "多个项目会共享使用这里的知识文档" in content
    assert "分析方法库" in content
    assert "上传知识文档" in content
    assert "问卷设计" in content
    assert "问卷分析" in content
    assert "报告写作" in content


def test_shared_knowledge_upload_supports_purpose_selection_without_front_matter(
    client: TestClient,
    tmp_path: Path,
):
    markdown_path = tmp_path / "plain-knowledge.md"
    markdown_path.write_text(
        "# 新手引导问卷建议\n\n这里是没有 front matter 的知识正文。",
        encoding="utf-8",
    )

    with markdown_path.open("rb") as handle:
        response = client.post(
            "/knowledge/upload",
            files={"file": ("plain-knowledge.md", handle, "text/markdown")},
            data={"purposes": ["questionnaire_design", "reporting"]},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert "upload_success=" in response.headers["location"]

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        document = session.exec(
            select(KnowledgeDocument).where(
                KnowledgeDocument.title == "新手引导问卷建议"
            )
        ).first()

    assert document is not None
    assert set(document.stages) == {"design", "report"}

    page = client.get("/knowledge")
    assert "新手引导问卷建议" in page.text
    assert "问卷设计" in page.text
    assert "报告写作" in page.text
