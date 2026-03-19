from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class ProjectKnowledgeSelection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_slug: str = Field(index=True)
    knowledge_document_id: int = Field(index=True)
    selected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
