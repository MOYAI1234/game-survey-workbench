from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from sqlmodel import Field, Session, SQLModel, select


class AnalysisRunRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    analysis_run_id: str = Field(index=True, unique=True)
    project_slug: str = Field(index=True)
    dataset_id: str = Field(index=True)
    status: str = "ready"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def get_analysis_run(analysis_run_id: str, *, workspace_root: Path) -> AnalysisRunRecord | None:
    from game_survey_workbench.db import get_engine

    engine = get_engine(workspace_root)
    with Session(engine) as session:
        return session.exec(
            select(AnalysisRunRecord).where(AnalysisRunRecord.analysis_run_id == analysis_run_id)
        ).first()
