from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ReportGenerateRequest(SQLModel):
    analysis_run_id: str


class ReportRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_slug: str = Field(index=True)
    analysis_run_id: str = Field(index=True)
    path: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
