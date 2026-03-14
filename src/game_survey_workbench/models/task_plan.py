from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class TaskItem(SQLModel):
    label: str
    status: str = "pending"


class TaskPlanPayload(SQLModel):
    tasks: list[TaskItem] = Field(default_factory=list)


class TaskPlanRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_slug: str = Field(index=True, unique=True)
    tasks: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
