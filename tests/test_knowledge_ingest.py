import asyncio
from pathlib import Path

import pytest
from sqlmodel import Session, select

from game_survey_workbench.db import get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.services.knowledge_ingest import (
    ingest_knowledge_file,
    retrieve_knowledge,
)


class BlockingVectorStore:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.allow_finish = asyncio.Event()

    async def add_chunks(self, **_: object) -> None:
        self.started.set()
        await self.allow_finish.wait()


class FailingVectorStore:
    async def add_chunks(self, **_: object) -> None:
        raise RuntimeError("embedding backend unavailable")


def _load_document(project_root: Path) -> KnowledgeDocument:
    engine = get_engine(project_root)
    with Session(engine) as session:
        return session.exec(select(KnowledgeDocument)).one()


@pytest.mark.anyio
async def test_ingest_knowledge_file_marks_document_indexing_then_ready_after_background_task(
    tmp_path: Path,
):
    source = tmp_path / "doc.md"
    source.write_text("# Title\n\nParagraph one.\n\nParagraph two.", encoding="utf-8")
    vector_store = BlockingVectorStore()

    result = ingest_knowledge_file(
        source,
        project_root=tmp_path,
        vector_store=vector_store,
    )

    assert result.status == "indexing"
    assert result.background_task is not None
    document = _load_document(tmp_path)
    assert document.title == "Title"
    assert document.index_status == "indexing"
    assert document.chunk_count == 0

    await vector_store.started.wait()
    vector_store.allow_finish.set()
    await result.background_task

    document = _load_document(tmp_path)
    assert document.index_status == "ready"
    assert document.index_error is None
    assert document.chunk_count == result.chunk_count


@pytest.mark.anyio
async def test_ingest_knowledge_file_marks_document_failed_when_background_task_errors(
    tmp_path: Path,
):
    source = tmp_path / "doc.md"
    source.write_text("# Title\n\nParagraph one.", encoding="utf-8")

    result = ingest_knowledge_file(
        source,
        project_root=tmp_path,
        vector_store=FailingVectorStore(),
    )

    assert result.status == "indexing"
    assert result.background_task is not None
    assert _load_document(tmp_path).index_status == "indexing"

    await result.background_task

    document = _load_document(tmp_path)
    assert document.index_status == "index_failed"
    assert "embedding backend unavailable" in (document.index_error or "")
    assert document.chunk_count == 0


def test_ingest_knowledge_file_keeps_sync_callers_working_with_ready_document(tmp_path: Path):
    source = tmp_path / "doc.md"
    source.write_text(
        "---\n"
        "title: Retention Framework\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - analysis\n"
        "tags:\n"
        "  - retention\n"
        "scenario: onboarding\n"
        "---\n"
        "Players need clear goals.\n",
        encoding="utf-8",
    )

    result = ingest_knowledge_file(source, project_root=tmp_path)
    document = _load_document(tmp_path)
    results = retrieve_knowledge(
        tmp_path,
        query="clear goals",
        stages=["analysis"],
        doc_types=["theory"],
        scenarios=["onboarding"],
    )

    assert result.background_task is None
    assert document.index_status == "ready"
    assert document.chunk_count >= 1
    assert results[0]["scenario"] == "onboarding"
    assert results[0]["tags"] == ["retention"]
