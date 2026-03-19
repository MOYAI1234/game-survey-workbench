from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import frontmatter
from sqlmodel import Session

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.retrieval.chunking import split_markdown
from game_survey_workbench.retrieval.store import LocalVectorStore, StoredChunk
from game_survey_workbench.services.knowledge_parser import parse_markdown_document
from game_survey_workbench.services.project_knowledge import (
    list_selected_knowledge_documents,
)
from game_survey_workbench.services.projects import get_project
from game_survey_workbench.services.workspace import bootstrap_workspace


@dataclass
class IngestKnowledgeResult:
    document_title: str
    chunk_count: int


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


def ingest_knowledge_file(source: Path, *, project_root: Path) -> IngestKnowledgeResult:
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
        )
        session.add(document)
        session.commit()

    store = LocalVectorStore(project_root / "artifacts" / "vector_store")
    store.save_chunks(
        [
            StoredChunk(
                document_title=parsed.title,
                content=chunk,
                stages=parsed.stages,
                doc_type=parsed.doc_type,
                tags=parsed.tags,
                scenario=parsed.scenario,
                priority=parsed.priority,
            )
            for chunk in chunks
        ]
    )

    return IngestKnowledgeResult(document_title=parsed.title, chunk_count=len(chunks))


def retrieve_knowledge(
    project_root: Path,
    *,
    query: str,
    stages: list[str] | None = None,
    doc_types: list[str] | None = None,
    scenarios: list[str] | None = None,
    top_k: int | None = None,
) -> list[dict]:
    store = LocalVectorStore(project_root / "artifacts" / "vector_store")
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
    top_k: int | None = None,
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

    store = LocalVectorStore(workspace_root / "artifacts" / "vector_store")
    results = store.query_layered(
        query=query,
        selected_document_titles=[document.title for document in selected_documents],
        task_stages=stages or [],
        top_domain_k=top_k or 5,
    )
    return results[:top_k] if top_k is not None else results
