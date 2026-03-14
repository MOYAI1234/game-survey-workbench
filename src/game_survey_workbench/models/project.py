from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class KnowledgePack(SQLModel):
    doc_types: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)


class ProjectCreate(SQLModel):
    slug: str
    name: str
    description: str = ""
    knowledge_pack: KnowledgePack = Field(default_factory=KnowledgePack)


class ProjectRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str
    description: str = ""
    status: str = "active"
    knowledge_pack: dict = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
