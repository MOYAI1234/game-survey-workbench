from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class ResearchBriefPayload(SQLModel):
    background: str = ""
    objectives: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    target_audience: str = ""
    success_criteria: str = ""


class ResearchBriefRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_slug: str = Field(index=True, unique=True)
    background: str = ""
    objectives: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    hypotheses: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    target_audience: str = ""
    success_criteria: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
