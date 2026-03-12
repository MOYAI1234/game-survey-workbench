from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlmodel import Session

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.questionnaire import (
    QuestionnaireDraftRequest,
    QuestionnaireSpecVersion,
)


def build_questionnaire_design_context(
    *,
    project_name: str,
    research_goal: str,
    hypotheses: list[str],
    knowledge_snippets: list[str],
) -> str:
    return "\n".join(
        [
            f"Project: {project_name}",
            f"Goal: {research_goal}",
            "Hypotheses:",
            *[f"- {item}" for item in hypotheses],
            "Knowledge:",
            *[f"- {item}" for item in knowledge_snippets],
        ]
    )


def save_questionnaire_draft(
    *,
    project_slug: str,
    project_name: str,
    payload: QuestionnaireDraftRequest,
    workspace_root: Path,
) -> QuestionnaireSpecVersion:
    create_db_and_tables(workspace_root)
    markdown_spec = build_questionnaire_design_context(
        project_name=project_name,
        research_goal=payload.research_goal,
        hypotheses=payload.hypotheses,
        knowledge_snippets=payload.knowledge_snippets,
    )
    version = QuestionnaireSpecVersion(
        project_slug=project_slug,
        version_id=str(uuid4()),
        research_goal=payload.research_goal,
        markdown_spec=markdown_spec,
    )
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        session.add(version)
        session.commit()
        session.refresh(version)

    version_dir = workspace_root / "projects" / project_slug / "questionnaire" / "versions"
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / f"{version.version_id}.md").write_text(markdown_spec, encoding="utf-8")
    return version
