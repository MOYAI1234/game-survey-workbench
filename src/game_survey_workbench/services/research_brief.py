from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.research_brief import (
    ResearchBriefPayload,
    ResearchBriefRecord,
)


def save_research_brief(
    *,
    project_slug: str,
    payload: ResearchBriefPayload,
    workspace_root: Path,
) -> ResearchBriefRecord:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        existing = session.exec(
            select(ResearchBriefRecord).where(
                ResearchBriefRecord.project_slug == project_slug
            )
        ).first()
        if existing is not None:
            existing.background = payload.background
            existing.objectives = payload.objectives
            existing.hypotheses = payload.hypotheses
            existing.target_audience = payload.target_audience
            existing.success_criteria = payload.success_criteria
            existing.updated_at = datetime.now(UTC)
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing

        record = ResearchBriefRecord(
            project_slug=project_slug,
            background=payload.background,
            objectives=payload.objectives,
            hypotheses=payload.hypotheses,
            target_audience=payload.target_audience,
            success_criteria=payload.success_criteria,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def get_research_brief(
    *, project_slug: str, workspace_root: Path
) -> ResearchBriefRecord | None:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        return session.exec(
            select(ResearchBriefRecord).where(
                ResearchBriefRecord.project_slug == project_slug
            )
        ).first()
