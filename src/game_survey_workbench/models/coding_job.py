from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class CodingJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_slug: str = Field(index=True)
    analysis_run_id: str = Field(index=True)
    question_column: str
    status: str = Field(default="queued")
    total_responses: int = 0
    coded_responses: int = 0
    batch_size: int = 80
    final_codebook_json: dict | None = Field(default=None, sa_column=Column(JSON))
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


class CodingBatch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(index=True)
    batch_index: int = 0
    status: str = Field(default="pending")
    input_texts_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    output_codes_json: dict | None = Field(default=None, sa_column=Column(JSON))
    retry_count: int = 0
    error_message: str | None = None
