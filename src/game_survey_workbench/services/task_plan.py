from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.task_plan import TaskPlanPayload, TaskPlanRecord


def save_task_plan(
    *,
    project_slug: str,
    payload: TaskPlanPayload,
    workspace_root: Path,
) -> TaskPlanRecord:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    tasks_data = [task.model_dump() for task in payload.tasks]
    with Session(engine) as session:
        existing = session.exec(
            select(TaskPlanRecord).where(TaskPlanRecord.project_slug == project_slug)
        ).first()
        if existing is not None:
            existing.tasks = tasks_data
            existing.updated_at = datetime.now(UTC)
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing

        record = TaskPlanRecord(project_slug=project_slug, tasks=tasks_data)
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def get_task_plan(*, project_slug: str, workspace_root: Path) -> TaskPlanRecord | None:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        return session.exec(
            select(TaskPlanRecord).where(TaskPlanRecord.project_slug == project_slug)
        ).first()
