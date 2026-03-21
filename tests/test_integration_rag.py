import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from game_survey_workbench.app import create_app
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.services.knowledge_ingest import (
    delete_knowledge_document,
    retrieve_knowledge,
)


def _wait_for_ready(workspace_root: Path, *, timeout_seconds: float = 5.0) -> KnowledgeDocument:
    deadline = time.time() + timeout_seconds
    engine = get_engine(workspace_root)
    while time.time() < deadline:
        with Session(engine) as session:
            document = session.exec(select(KnowledgeDocument)).first()
            if document is not None and document.index_status == "ready":
                return document
            if document is not None and document.index_status == "index_failed":
                raise AssertionError(document.index_error or "indexing failed")
        time.sleep(0.05)
    raise AssertionError("knowledge document did not reach ready status in time")


def test_upload_query_and_delete_document_with_chroma_backend(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_EMBEDDING_API_KEY", "fake")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_EMBEDDING_BASE_URL", "http://localhost/fake")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_EMBEDDING_MODEL", "fake-embedding")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_RELEVANCE_THRESHOLD", "1.4")

    markdown = (
        "---\n"
        "title: Season Pass Research\n"
        "doc_type: research\n"
        "stage:\n"
        "  - analysis\n"
        "---\n\n"
        "# Season Pass\n\n"
        "Season pass value depends on reward clarity and long-term motivation.\n"
        "Players compare pricing against visible progression rewards.\n"
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/knowledge/upload",
            files={"file": ("season-pass.md", markdown.encode("utf-8"), "text/markdown")},
            data={"purposes": "analysis"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    document = _wait_for_ready(tmp_path)

    results = retrieve_knowledge(
        tmp_path,
        query="reward clarity and pricing",
        stages=["analysis"],
        doc_types=["research"],
    )

    assert results
    assert results[0]["document_title"] == "Season Pass Research"

    delete_knowledge_document(document.id, project_root=tmp_path)

    assert retrieve_knowledge(
        tmp_path,
        query="reward clarity and pricing",
        stages=["analysis"],
        doc_types=["research"],
    ) == []
