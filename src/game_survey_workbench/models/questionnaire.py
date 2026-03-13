from __future__ import annotations

from datetime import datetime, UTC
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class QuestionnaireDraftRequest(SQLModel):
    research_goal: str
    hypotheses: list[str] = Field(default_factory=list)
    knowledge_snippets: list[str] = Field(default_factory=list)


class QuestionnaireSpecVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_slug: str = Field(index=True)
    version_id: str = Field(index=True, unique=True)
    research_goal: str
    markdown_spec: str
    citations: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    retrieved_snippets: list[dict] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
