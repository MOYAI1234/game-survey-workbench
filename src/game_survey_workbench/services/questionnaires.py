from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlmodel import Session

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.errors import NoKnowledgeMatchedError, ProjectNotFoundError
from game_survey_workbench.llm.client import LLMClient
from game_survey_workbench.models.questionnaire import (
    QuestionnaireDraftRequest,
    QuestionnaireSpecVersion,
)
from game_survey_workbench.services.knowledge_ingest import retrieve_project_knowledge
from game_survey_workbench.services.projects import get_project


def format_knowledge_item(item: str | dict) -> str:
    if isinstance(item, str):
        return item

    title = item.get("document_title", "Unknown Source")
    content = item.get("content", "").strip()
    tags = item.get("tags", [])
    tag_text = f" [tags: {', '.join(tags)}]" if tags else ""
    return f"{title}{tag_text}: {content}".strip()


def build_questionnaire_design_context(
    *,
    project_name: str,
    research_goal: str,
    hypotheses: list[str],
    knowledge_snippets: list[str | dict],
) -> str:
    return "\n".join(
        [
            f"Project: {project_name}",
            f"Goal: {research_goal}",
            "Hypotheses:",
            *[f"- {item}" for item in hypotheses],
            "Knowledge:",
            *[f"- {format_knowledge_item(item)}" for item in knowledge_snippets],
        ]
    )


def build_questionnaire_markdown(*, llm_output: str, citations: list[dict]) -> str:
    sections = [llm_output.strip(), "", "## Knowledge Basis"]
    for citation in citations:
        title = citation.get("document_title", "Unknown Source")
        content = citation.get("content", "").strip()
        sections.append(f"- {title}: {content}")
    return "\n".join(sections).strip()


def load_questionnaire_prompt() -> str:
    prompt_path = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "questionnaire_design.md"
    return prompt_path.read_text(encoding="utf-8").strip()


def save_questionnaire_draft(
    *,
    project_slug: str,
    project_name: str,
    payload: QuestionnaireDraftRequest,
    workspace_root: Path,
    markdown_spec: str | None = None,
    citations: list[dict] | None = None,
    retrieved_snippets: list[dict] | None = None,
) -> QuestionnaireSpecVersion:
    create_db_and_tables(workspace_root)
    final_markdown = markdown_spec or build_questionnaire_design_context(
        project_name=project_name,
        research_goal=payload.research_goal,
        hypotheses=payload.hypotheses,
        knowledge_snippets=payload.knowledge_snippets,
    )
    version = QuestionnaireSpecVersion(
        project_slug=project_slug,
        version_id=str(uuid4()),
        research_goal=payload.research_goal,
        markdown_spec=final_markdown,
        citations=citations or [],
        retrieved_snippets=retrieved_snippets or [],
    )
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        session.add(version)
        session.commit()
        session.refresh(version)

    version_dir = workspace_root / "projects" / project_slug / "questionnaire" / "versions"
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / f"{version.version_id}.md").write_text(final_markdown, encoding="utf-8")
    return version


def generate_questionnaire_draft(
    *,
    project_slug: str,
    payload: QuestionnaireDraftRequest,
    workspace_root: Path,
    client: LLMClient,
) -> QuestionnaireSpecVersion:
    project = get_project(workspace_root=workspace_root, project_slug=project_slug)
    if project is None:
        raise ProjectNotFoundError("Project not found.")

    query_parts = [payload.research_goal, *payload.hypotheses]
    snippets = retrieve_project_knowledge(
        workspace_root=workspace_root,
        project_slug=project_slug,
        query=" ".join(part for part in query_parts if part),
        stages=["design"],
    )
    if not snippets:
        snippets = retrieve_project_knowledge(
            workspace_root=workspace_root,
            project_slug=project_slug,
            query="",
            stages=["design"],
        )
    if not snippets:
        raise NoKnowledgeMatchedError("No knowledge matched this questionnaire request.")

    context = build_questionnaire_design_context(
        project_name=project.name,
        research_goal=payload.research_goal,
        hypotheses=payload.hypotheses,
        knowledge_snippets=snippets,
    )
    prompt = load_questionnaire_prompt()
    llm_output = client.generate(f"{prompt}\n\n{context}")
    markdown = build_questionnaire_markdown(llm_output=llm_output, citations=snippets)
    return save_questionnaire_draft(
        project_slug=project_slug,
        project_name=project.name,
        payload=payload,
        workspace_root=workspace_root,
        markdown_spec=markdown,
        citations=snippets,
        retrieved_snippets=snippets,
    )
