from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, Session, SQLModel, select


class QuestionColumnSchema(SQLModel):
    column_role: str = "question"
    question_type: str
    include_in_analysis: bool = True
    other_text_column: str | None = None
    reason: str | None = None


class ImportedDataset(SQLModel):
    dataset_id: str
    project_slug: str
    source_path: str
    question_columns: dict[str, QuestionColumnSchema]
    analysis_run_id: str | None = None


class DatasetRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    dataset_id: str = Field(index=True, unique=True)
    project_slug: str = Field(index=True)
    source_path: str
    dataset_schema: dict = Field(default_factory=dict, sa_column=Column(JSON))
    analysis_run_id: str | None = None
    format_type: str | None = None
    column_overrides_json: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def get_dataset_record(dataset_id: str, *, workspace_root: Path) -> DatasetRecord | None:
    from game_survey_workbench.db import get_engine

    engine = get_engine(workspace_root)
    with Session(engine) as session:
        return session.exec(
            select(DatasetRecord).where(DatasetRecord.dataset_id == dataset_id)
        ).first()
