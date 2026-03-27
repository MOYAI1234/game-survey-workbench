from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.services.workspace import bootstrap_workspace


def test_knowledge_page_shows_index_status_badges_and_retry_button(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    indexing_path = knowledge_dir / "indexing.md"
    ready_path = knowledge_dir / "ready.md"
    failed_path = knowledge_dir / "failed.md"
    indexing_path.write_text("indexing", encoding="utf-8")
    ready_path.write_text("ready", encoding="utf-8")
    failed_path.write_text("failed", encoding="utf-8")

    with Session(engine) as session:
        session.add(
            KnowledgeDocument(
                source_path=str(indexing_path),
                title="正在索引的文档",
                doc_type="guide",
                stages=["design"],
                index_status="indexing",
            )
        )
        session.add(
            KnowledgeDocument(
                source_path=str(ready_path),
                title="已完成文档",
                doc_type="research",
                stages=["analysis"],
                index_status="ready",
                chunk_count=1234,
            )
        )
        session.add(
            KnowledgeDocument(
                source_path=str(failed_path),
                title="失败文档",
                doc_type="theory",
                stages=["report"],
                index_status="index_failed",
                index_error="embedding backend unavailable",
            )
        )
        session.commit()

    with TestClient(create_app()) as client:
        response = client.get("/knowledge")

    assert response.status_code == 200
    html = response.text
    assert 'class="knowledge-toolbar"' in html
    assert 'class="knowledge-document-list"' in html
    assert 'class="knowledge-document-card"' in html
    assert 'class="status-pill status-pill-running"' in html
    assert 'class="status-pill status-pill-ready"' in html
    assert 'class="status-pill status-pill-error"' in html
    assert "正在建立索引..." in html
    assert "已就绪 · 1,234 chunks" in html
    assert "索引失败" in html
    assert "embedding backend unavailable" in html
    assert 'action="/knowledge/3/retry"' in html
    assert "重试索引" in html
    assert 'action="/knowledge/2/delete"' in html
    assert 'data-confirm-text="确认将这篇文档移出共享知识库吗？"' in html
    assert "移出共享知识库" in html
    assert ".epub" in html
    assert "图片型 PDF" in html


def test_delete_knowledge_document_route_removes_file_and_record(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    knowledge_path = tmp_path / "knowledge" / "removable.md"
    knowledge_path.parent.mkdir(parents=True, exist_ok=True)
    knowledge_path.write_text("---\ntitle: 待移除文档\n---\n正文", encoding="utf-8")

    with Session(engine) as session:
        document = KnowledgeDocument(
            source_path=str(knowledge_path),
            title="待移除文档",
            doc_type="guide",
            stages=["analysis"],
            index_status="ready",
            chunk_count=1,
        )
        session.add(document)
        session.commit()
        session.refresh(document)
        document_id = int(document.id or 0)

    with TestClient(create_app()) as client:
        response = client.post(f"/knowledge/{document_id}/delete", follow_redirects=False)

    assert response.status_code == 303
    assert "upload_success=" in response.headers["location"]
    assert not knowledge_path.exists()
    with Session(engine) as session:
        assert session.get(KnowledgeDocument, document_id) is None


def test_knowledge_page_cleans_missing_file_records(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        session.add(
            KnowledgeDocument(
                source_path=str(tmp_path / "knowledge" / "missing.md"),
                title="僵尸记录",
                doc_type="experience",
                stages=["design"],
                index_status="ready",
                chunk_count=4,
            )
        )
        session.commit()

    with TestClient(create_app()) as client:
        response = client.get("/knowledge")

    assert response.status_code == 200
    assert "僵尸记录" not in response.text
    with Session(engine) as session:
        documents = list(session.exec(select(KnowledgeDocument)).all())
    assert documents == []


def test_knowledge_page_uses_workspace_sections_when_empty(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)

    with TestClient(create_app()) as client:
        response = client.get("/knowledge")

    assert response.status_code == 200
    html = response.text
    assert 'class="knowledge-hero"' in html
    assert 'class="knowledge-toolbar"' in html
    assert 'class="knowledge-document-list"' in html
    assert "当前没有符合筛选条件的知识文档" in html
