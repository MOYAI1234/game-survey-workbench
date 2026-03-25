from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import frontmatter
from sqlmodel import Session

from game_survey_workbench.config import Settings, get_settings
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.retrieval.embeddings import (
    DeterministicEmbeddingClient,
    EmbeddingClient,
)
from game_survey_workbench.retrieval.chunking import ChunkResult, split_markdown
from game_survey_workbench.retrieval.store import (
    DEFAULT_PROJECT_KNOWLEDGE_TOP_K,
    ChromaVectorStore,
    LocalVectorStore,
    StoredChunk,
)
from game_survey_workbench.services.knowledge_parser import parse_markdown_document
from game_survey_workbench.services.project_knowledge import (
    list_selected_knowledge_documents,
)
from game_survey_workbench.services.projects import get_project
from game_survey_workbench.services.workspace import bootstrap_workspace


@dataclass
class IngestKnowledgeResult:
    document_id: int
    document_title: str
    chunk_count: int
    status: str
    background_task: asyncio.Task[Any] | None = None


class LocalVectorStoreAdapter:
    def __init__(self, root: Path) -> None:
        self.store = LocalVectorStore(root)

    def add_chunks(
        self,
        *,
        document_id: int,
        document_title: str,
        doc_type: str,
        stages: list[str],
        tags: list[str],
        chunks: list[ChunkResult],
        scenario: str | None = None,
        priority: int = 0,
    ) -> None:
        del document_id
        self.store.save_chunks(
            [
                StoredChunk(
                    document_title=document_title,
                    content=chunk.content,
                    stages=stages,
                    doc_type=doc_type,
                    tags=tags,
                    scenario=scenario,
                    priority=priority,
                )
                for chunk in chunks
            ]
        )

    def delete_document(self, document_id: int) -> None:
        del document_id
        return None


def _get_effective_settings(project_root: Path) -> Settings:
    settings = get_settings()
    if settings.workspace_root != project_root:
        settings.workspace_root = project_root
        settings.chroma_path = project_root / "artifacts" / "chroma_db"
        settings.legacy_chunks_path = (
            project_root / "artifacts" / "vector_store" / "chunks.json"
        )
    return settings


def _build_embedding_client(settings: Settings) -> Any:
    if settings.embedding_api_key == "fake":
        return DeterministicEmbeddingClient(dimensions=settings.embedding_dimensions)
    return EmbeddingClient(
        api_key=settings.embedding_api_key or "",
        base_url=settings.embedding_base_url,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
    )


def _build_ingest_store(project_root: Path) -> Any:
    settings = _get_effective_settings(project_root)
    if settings.embedding_api_key:
        import chromadb

        client = chromadb.PersistentClient(path=str(settings.chroma_path))
        collection = client.get_or_create_collection("knowledge_chunks")
        return ChromaVectorStore(
            collection=collection,
            embedding_client=_build_embedding_client(settings),
            relevance_threshold=settings.relevance_threshold,
        )
    return LocalVectorStoreAdapter(project_root / "artifacts" / "vector_store")


def _build_query_store(project_root: Path) -> Any:
    settings = _get_effective_settings(project_root)
    if settings.embedding_api_key:
        import chromadb

        client = chromadb.PersistentClient(path=str(settings.chroma_path))
        collection = client.get_or_create_collection("knowledge_chunks")
        return ChromaVectorStore(
            collection=collection,
            embedding_client=_build_embedding_client(settings),
            relevance_threshold=settings.relevance_threshold,
        )
    return LocalVectorStore(project_root / "artifacts" / "vector_store")


PURPOSE_STAGE_MAP = {
    "questionnaire_design": "design",
    "analysis": "analysis",
    "reporting": "report",
}

STAGE_LABEL_MAP = {
    "design": "问卷设计",
    "analysis": "问卷分析",
    "report": "报告写作",
}


def _normalize_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    return [item for item in value if item]


def _infer_title_and_body(*, raw: str, fallback_name: str) -> tuple[str, str]:
    post = frontmatter.loads(raw)
    if post.get("title"):
        return str(post["title"]), post.content.strip()

    body = post.content.strip()
    if body.startswith("# "):
        first_line, _, rest = body.partition("\n")
        heading_title = first_line.removeprefix("# ").strip()
        if heading_title:
            return heading_title, rest.strip()

    return Path(fallback_name).stem or "Untitled", body


def build_ingest_ready_markdown(
    *,
    raw: str,
    filename: str,
    purposes: list[str] | None = None,
) -> str:
    post = frontmatter.loads(raw)
    selected_purposes = purposes or []
    mapped_stages = [
        PURPOSE_STAGE_MAP[purpose]
        for purpose in selected_purposes
        if purpose in PURPOSE_STAGE_MAP
    ]
    existing_stages = _normalize_list(post.get("stage"))
    title, body = _infer_title_and_body(raw=raw, fallback_name=filename)
    tags = _normalize_list(post.get("tags"))

    metadata = {
        "title": title,
        "doc_type": post.get("doc_type", "guide"),
        "stage": mapped_stages or existing_stages,
        "tags": tags,
        "priority": int(post.get("priority", 0)),
    }
    if post.get("scenario") is not None:
        metadata["scenario"] = post.get("scenario")

    return frontmatter.dumps(frontmatter.Post(body or title, **metadata))


def ingest_knowledge_file(
    source: Path,
    *,
    project_root: Path,
    vector_store: Any | None = None,
) -> IngestKnowledgeResult:
    bootstrap_workspace(project_root)
    create_db_and_tables(project_root)
    raw = source.read_text(encoding="utf-8")
    parsed = parse_markdown_document(raw)
    body = parsed.body
    if source.suffix.lower() == ".md" and parsed.title == "Untitled" and raw.startswith("# "):
        first_line, _, rest = raw.partition("\n")
        parsed.title = first_line.removeprefix("# ").strip() or parsed.title
        body = rest.strip()

    chunks = split_markdown(body)
    engine = get_engine(project_root)

    with Session(engine) as session:
        document = KnowledgeDocument(
            source_path=str(source),
            title=parsed.title,
            doc_type=parsed.doc_type,
            stages=parsed.stages,
            tags=parsed.tags,
            scenario=parsed.scenario,
            priority=parsed.priority,
            index_status="indexing",
            index_error=None,
            chunk_count=0,
        )
        session.add(document)
        session.commit()
        session.refresh(document)

    store = vector_store or _build_ingest_store(project_root)
    task_body = _finalize_document_index(
        project_root=project_root,
        document_id=int(document.id or 0),
        document_title=parsed.title,
        doc_type=parsed.doc_type,
        stages=parsed.stages,
        tags=parsed.tags,
        scenario=parsed.scenario,
        priority=parsed.priority,
        chunks=chunks,
        vector_store=store,
    )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(task_body)
        status = _get_document_status(project_root=project_root, document_id=int(document.id or 0))
        return IngestKnowledgeResult(
            document_id=int(document.id or 0),
            document_title=parsed.title,
            chunk_count=len(chunks),
            status=status,
            background_task=None,
        )

    background_task = asyncio.create_task(task_body)
    return IngestKnowledgeResult(
        document_id=int(document.id or 0),
        document_title=parsed.title,
        chunk_count=len(chunks),
        status="indexing",
        background_task=background_task,
    )


async def _finalize_document_index(
    *,
    project_root: Path,
    document_id: int,
    document_title: str,
    doc_type: str,
    stages: list[str],
    tags: list[str],
    scenario: str | None,
    priority: int,
    chunks: list[ChunkResult],
    vector_store: Any,
) -> None:
    try:
        add_kwargs = dict(
            document_id=document_id,
            document_title=document_title,
            doc_type=doc_type,
            stages=stages,
            tags=tags,
            chunks=chunks,
            scenario=scenario,
            priority=priority,
        )
        if hasattr(vector_store, "aadd_chunks"):
            await vector_store.aadd_chunks(**add_kwargs)
        else:
            result = vector_store.add_chunks(**add_kwargs)
            if inspect.isawaitable(result):
                await result
        _update_document_index(
            project_root=project_root,
            document_id=document_id,
            index_status="ready",
            index_error=None,
            chunk_count=len(chunks),
        )
    except Exception as exc:
        _update_document_index(
            project_root=project_root,
            document_id=document_id,
            index_status="index_failed",
            index_error=str(exc),
            chunk_count=0,
        )


def _update_document_index(
    *,
    project_root: Path,
    document_id: int,
    index_status: str,
    index_error: str | None,
    chunk_count: int,
) -> None:
    engine = get_engine(project_root)
    with Session(engine) as session:
        document = session.get(KnowledgeDocument, document_id)
        if document is None:
            return
        document.index_status = index_status
        document.index_error = index_error
        document.chunk_count = chunk_count
        session.add(document)
        session.commit()


def _get_document_status(*, project_root: Path, document_id: int) -> str:
    engine = get_engine(project_root)
    with Session(engine) as session:
        document = session.get(KnowledgeDocument, document_id)
        return document.index_status if document is not None else "index_failed"


def retrieve_knowledge(
    project_root: Path,
    *,
    query: str,
    stages: list[str] | None = None,
    doc_types: list[str] | None = None,
    scenarios: list[str] | None = None,
    top_k: int | None = None,
) -> list[dict]:
    store = _build_query_store(project_root)
    return store.query(
        query,
        stages=stages,
        doc_types=doc_types,
        scenarios=scenarios,
        top_k=top_k,
    )


def retrieve_project_knowledge(
    *,
    workspace_root: Path,
    project_slug: str,
    query: str,
    stages: list[str] | None = None,
    top_k: int | None = DEFAULT_PROJECT_KNOWLEDGE_TOP_K,
) -> list[dict]:
    project = get_project(workspace_root=workspace_root, project_slug=project_slug)
    if project is None:
        return []

    selected_documents = list_selected_knowledge_documents(
        workspace_root=workspace_root,
        project_slug=project_slug,
    )
    if not selected_documents:
        return []

    store = _build_query_store(workspace_root)
    results = store.query_layered(
        query=query,
        selected_document_titles=[document.title for document in selected_documents],
        task_stages=stages or [],
        top_method_k=top_k or DEFAULT_PROJECT_KNOWLEDGE_TOP_K,
        top_domain_k=top_k or DEFAULT_PROJECT_KNOWLEDGE_TOP_K,
    )
    return results[:top_k] if top_k is not None else results


def delete_knowledge_document(document_id: int | None, *, project_root: Path) -> None:
    if document_id is None:
        return

    store = _build_ingest_store(project_root)
    engine = get_engine(project_root)
    with Session(engine) as session:
        document = session.get(KnowledgeDocument, int(document_id))
        if document is None:
            return
        source_path = Path(document.source_path)
        if source_path.exists() and source_path.is_file():
            source_path.unlink()
        if hasattr(store, "delete_document"):
            store.delete_document(int(document_id))
        session.delete(document)
        session.commit()
