from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectCreate, ProjectRecord
from game_survey_workbench.services.workspace import bootstrap_workspace


def create_project(payload: ProjectCreate, *, workspace_root: Path) -> ProjectRecord:
    bootstrap_workspace(workspace_root)
    create_db_and_tables(workspace_root)
    project_root = workspace_root / "projects" / payload.slug
    for child in ("questionnaire", "data", "analysis", "reports", "assets"):
        (project_root / child).mkdir(parents=True, exist_ok=True)

    engine = get_engine(workspace_root)
    with Session(engine) as session:
        existing = session.exec(
            select(ProjectRecord).where(ProjectRecord.slug == payload.slug)
        ).first()
        if existing is not None:
            return existing

        record = ProjectRecord(
            slug=payload.slug,
            name=payload.name,
            description=payload.description,
            language=payload.language,
            knowledge_pack=payload.knowledge_pack.model_dump(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def get_project(*, workspace_root: Path, project_slug: str) -> ProjectRecord | None:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        return session.exec(
            select(ProjectRecord).where(ProjectRecord.slug == project_slug)
        ).first()


def list_projects(*, workspace_root: Path) -> list[ProjectRecord]:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        return list(session.exec(select(ProjectRecord).order_by(ProjectRecord.id)).all())
