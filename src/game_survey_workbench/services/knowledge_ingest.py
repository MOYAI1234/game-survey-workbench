from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.retrieval.chunking import split_markdown
from game_survey_workbench.retrieval.store import LocalVectorStore, StoredChunk
from game_survey_workbench.services.knowledge_parser import parse_markdown_document
from game_survey_workbench.services.projects import get_project
from game_survey_workbench.services.workspace import bootstrap_workspace


@dataclass
class IngestKnowledgeResult:
    document_title: str
    chunk_count: int


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
) -> list[dict]:
    store = LocalVectorStore(project_root / "artifacts" / "vector_store")
    return store.query(
        query,
        stages=stages,
        doc_types=doc_types,
        scenarios=scenarios,
    )


def retrieve_project_knowledge(
    *,
    workspace_root: Path,
    project_slug: str,
    query: str,
    stages: list[str] | None = None,
) -> list[dict]:
    project = get_project(workspace_root=workspace_root, project_slug=project_slug)
    if project is None:
        return []

    knowledge_pack = project.knowledge_pack or {}
    return retrieve_knowledge(
        workspace_root,
        query=query,
        stages=stages,
        doc_types=knowledge_pack.get("doc_types", []),
        scenarios=knowledge_pack.get("scenarios", []),
    )
