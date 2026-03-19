from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.errors import ProjectNotFoundError
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.models.project_knowledge_selection import (
    ProjectKnowledgeSelection,
)
from game_survey_workbench.services.projects import get_project


def _deduplicate_ids(values: list[int]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def list_selected_knowledge_document_ids(
    *,
    workspace_root: Path,
    project_slug: str,
) -> list[int]:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        selections = list(
            session.exec(
                select(ProjectKnowledgeSelection)
                .where(ProjectKnowledgeSelection.project_slug == project_slug)
                .order_by(ProjectKnowledgeSelection.id)
            ).all()
        )
    return [selection.knowledge_document_id for selection in selections]


def replace_project_knowledge_selection(
    *,
    workspace_root: Path,
    project_slug: str,
    knowledge_document_ids: list[int],
) -> list[ProjectKnowledgeSelection]:
    create_db_and_tables(workspace_root)
    project = get_project(workspace_root=workspace_root, project_slug=project_slug)
    if project is None:
        raise ProjectNotFoundError("Project not found.")

    deduped_ids = _deduplicate_ids(knowledge_document_ids)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        existing = list(
            session.exec(
                select(ProjectKnowledgeSelection).where(
                    ProjectKnowledgeSelection.project_slug == project_slug
                )
            ).all()
        )
        for item in existing:
            session.delete(item)

        valid_ids = set(
            session.exec(select(KnowledgeDocument.id)).all()
        )
        created: list[ProjectKnowledgeSelection] = []
        for document_id in deduped_ids:
            if document_id not in valid_ids:
                continue
            record = ProjectKnowledgeSelection(
                project_slug=project_slug,
                knowledge_document_id=document_id,
            )
            session.add(record)
            created.append(record)

        session.commit()
        for record in created:
            session.refresh(record)
        return created
