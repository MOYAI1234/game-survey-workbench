from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.research_wave import ResearchWave


def create_research_wave(
    *,
    workspace_root: Path,
    project_slug: str,
    name: str,
    goal_summary: str = "",
) -> ResearchWave:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    now = datetime.now(UTC)

    with Session(engine) as session:
        existing_waves = list(
            session.exec(
                select(ResearchWave)
                .where(ResearchWave.project_slug == project_slug)
                .order_by(ResearchWave.id)
            ).all()
        )
        for wave in existing_waves:
            wave.is_current = False
            wave.updated_at = now
            session.add(wave)

        wave = ResearchWave(
            project_slug=project_slug,
            name=name,
            goal_summary=goal_summary,
            is_current=True,
            created_at=now,
            updated_at=now,
        )
        session.add(wave)
        session.commit()
        session.refresh(wave)
        return wave


def list_research_waves(*, workspace_root: Path, project_slug: str) -> list[ResearchWave]:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        return list(
            session.exec(
                select(ResearchWave)
                .where(ResearchWave.project_slug == project_slug)
                .order_by(ResearchWave.updated_at.desc(), ResearchWave.id.desc())
            ).all()
        )


def get_current_research_wave(
    *,
    workspace_root: Path,
    project_slug: str,
) -> ResearchWave | None:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        current = session.exec(
            select(ResearchWave)
            .where(
                ResearchWave.project_slug == project_slug,
                ResearchWave.is_current.is_(True),
            )
            .order_by(ResearchWave.updated_at.desc(), ResearchWave.id.desc())
        ).first()
        if current is not None:
            return current

        return session.exec(
            select(ResearchWave)
            .where(ResearchWave.project_slug == project_slug)
            .order_by(ResearchWave.updated_at.desc(), ResearchWave.id.desc())
        ).first()


def set_current_research_wave(
    *,
    workspace_root: Path,
    project_slug: str,
    wave_id: int,
) -> ResearchWave:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    now = datetime.now(UTC)

    with Session(engine) as session:
        waves = list(
            session.exec(
                select(ResearchWave).where(ResearchWave.project_slug == project_slug)
            ).all()
        )
        target: ResearchWave | None = None
        for wave in waves:
            is_target = wave.id == wave_id
            wave.is_current = is_target
            wave.updated_at = now
            session.add(wave)
            if is_target:
                target = wave

        if target is None:
            raise ValueError("Research wave not found.")

        session.commit()
        session.refresh(target)
        return target
