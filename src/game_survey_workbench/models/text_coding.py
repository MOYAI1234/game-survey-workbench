from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class TextCodingRequest(SQLModel):
    question_column: str
    responses: list[str] | None = None


class CodingResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    analysis_run_id: str = Field(index=True)
    question_column: str
    themes: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    uncoded_count: int = 0
    citations: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
