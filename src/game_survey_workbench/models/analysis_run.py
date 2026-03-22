from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, Session, SQLModel, select

from game_survey_workbench.errors import AnalysisRunNotFoundError


class AnalysisRunRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    analysis_run_id: str = Field(index=True, unique=True)
    project_slug: str = Field(index=True)
    wave_id: Optional[int] = Field(default=None, index=True)
    dataset_id: str = Field(index=True)
    status: str = "ready"
    workflow_state: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def get_analysis_run(analysis_run_id: str, *, workspace_root: Path) -> AnalysisRunRecord | None:
    from game_survey_workbench.db import get_engine

    engine = get_engine(workspace_root)
    with Session(engine) as session:
        return session.exec(
            select(AnalysisRunRecord).where(AnalysisRunRecord.analysis_run_id == analysis_run_id)
        ).first()


def require_analysis_run(analysis_run_id: str, *, workspace_root: Path) -> AnalysisRunRecord:
    analysis_run = get_analysis_run(analysis_run_id, workspace_root=workspace_root)
    if analysis_run is None:
        raise AnalysisRunNotFoundError("Analysis run not found.")
    return analysis_run
