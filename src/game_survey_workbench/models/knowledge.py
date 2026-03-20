from __future__ import annotations

from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class KnowledgeDocument(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_path: str
    title: str
    doc_type: str = "experience"
    stages: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    scenario: Optional[str] = None
    priority: int = 0
    source_format: Optional[str] = None
    index_status: str = "pending"
    index_error: Optional[str] = None
    chunk_count: int = 0
