from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlmodel import Session

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.errors import (
    NoKnowledgeMatchedError,
    NoKnowledgeSelectedError,
    ProjectNotFoundError,
)
from game_survey_workbench.llm.client import LLMClient
from game_survey_workbench.models.questionnaire import (
    QuestionnaireDraftRequest,
    QuestionnaireSpecVersion,
)
from game_survey_workbench.services.knowledge_ingest import retrieve_project_knowledge
from game_survey_workbench.services.project_knowledge import (
    list_selected_knowledge_document_ids,
)
from game_survey_workbench.services.projects import get_project
from game_survey_workbench.services.research_brief import get_research_brief
from game_survey_workbench.services.research_waves import get_current_research_wave


def format_knowledge_item(item: str | dict) -> str:
    if isinstance(item, str):
        return item

    title = item.get("document_title", "Unknown Source")
    content = item.get("content", "").strip()
    tags = item.get("tags", [])
    tag_text = f" [tags: {', '.join(tags)}]" if tags else ""
    return f"{title}{tag_text}: {content}".strip()


def _language_suffix(language: str, *, bilingual: bool = False) -> str:
    if bilingual:
        return (
            "\n\n## Language Instruction\n"
            "Output the complete questionnaire in English first. "
            "Then add a horizontal divider (---), and provide the complete "
            "Chinese translation of the same questionnaire below. "
            "Both versions must be complete and independently usable."
        )
    if language == "zh":
        return (
            "\n\n## Language Instruction\n"
            "Output the entire questionnaire in Chinese (简体中文). "
            "Section headings, question text, and diagnostic notes must all be in Chinese."
        )
    return (
        "\n\n## Language Instruction\n"
        "Output the entire questionnaire in English."
    )


def build_questionnaire_design_context(
    *,
    project_name: str,
    research_goal: str,
    hypotheses: list[str],
    knowledge_snippets: list[str | dict],
    brief_background: str = "",
    brief_target_audience: str = "",
    language: str = "zh",
    bilingual: bool = False,
) -> str:
    parts = [
        f"Project: {project_name}",
        f"Goal: {research_goal}",
    ]
    if brief_background:
        parts.append(f"Background: {brief_background}")
    if brief_target_audience:
        parts.append(f"Target Audience: {brief_target_audience}")
    parts.extend(
        [
            "Hypotheses:",
            *[f"- {item}" for item in hypotheses],
            "Knowledge:",
            *[f"- {format_knowledge_item(item)}" for item in knowledge_snippets],
        ]
    )
    return "\n".join(parts) + _language_suffix(language, bilingual=bilingual)


def build_questionnaire_markdown(*, llm_output: str, citations: list[dict]) -> str:
    sections = [llm_output.strip(), "", "## Knowledge Basis"]
    for citation in citations:
        title = citation.get("document_title", "Unknown Source")
        content = citation.get("content", "").strip()
        sections.append(f"- {title}: {content}")
    return "\n".join(sections).strip()


def build_questionnaire_display_markdown(markdown_spec: str) -> str:
    display_markdown, _separator, _knowledge_basis = markdown_spec.partition("\n## Knowledge Basis")
    return display_markdown.strip()


def build_provenance_cards(snippets: list[str | dict]) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for snippet in snippets:
        if isinstance(snippet, str):
            cards.append(
                {
                    "title": "项目知识",
                    "pool_label": "项目知识",
                    "excerpt": snippet[:180].rstrip(),
                }
            )
            continue
        title = snippet.get("document_title", "Unknown Source")
        retrieval_pool = snippet.get("retrieval_pool")
        content = snippet.get("content", "").strip()
        excerpt = content[:180].rstrip()
        if len(content) > 180:
            excerpt = f"{excerpt}..."
        cards.append(
            {
                "title": title,
                "pool_label": (
                    "方法论池"
                    if retrieval_pool == "method"
                    else "领域知识池"
                    if retrieval_pool == "domain"
                    else "项目知识"
                ),
                "excerpt": excerpt,
            }
        )
    return cards


def load_questionnaire_prompt() -> str:
    prompt_path = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "questionnaire_design.md"
    return prompt_path.read_text(encoding="utf-8").strip()


def load_questionnaire_refine_prompt() -> str:
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "questionnaire_refine.txt"
    return prompt_path.read_text(encoding="utf-8").strip()


def save_questionnaire_draft(
    *,
    project_slug: str,
    project_name: str,
    payload: QuestionnaireDraftRequest,
    workspace_root: Path,
    wave_id: int | None = None,
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
        wave_id=wave_id,
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

    version_dir = workspace_root / "projects" / project_slug / "questionnaire"
    if wave_id is not None:
        version_dir = version_dir / "waves" / str(wave_id)
    version_dir = version_dir / "versions"
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / f"{version.version_id}.md").write_text(final_markdown, encoding="utf-8")
    return version


def generate_questionnaire_draft(
    *,
    project_slug: str,
    payload: QuestionnaireDraftRequest,
    workspace_root: Path,
    client: LLMClient,
    bilingual: bool = False,
) -> QuestionnaireSpecVersion:
    project = get_project(workspace_root=workspace_root, project_slug=project_slug)
    if project is None:
        raise ProjectNotFoundError("Project not found.")
    if not list_selected_knowledge_document_ids(
        workspace_root=workspace_root,
        project_slug=project_slug,
    ):
        raise NoKnowledgeSelectedError("项目尚未选择任何知识文档，请先到项目页完成知识选择。")

    query_parts = [payload.research_goal, *payload.hypotheses]
    snippets = retrieve_project_knowledge(
        workspace_root=workspace_root,
        project_slug=project_slug,
        query=" ".join(part for part in query_parts if part),
        stages=["design"],
    )
    if not snippets:
        raise NoKnowledgeMatchedError("已选知识中没有命中当前问卷任务所需的内容，请调整项目知识选择。")

    brief = get_research_brief(
        project_slug=project_slug,
        workspace_root=workspace_root,
    )
    current_wave = get_current_research_wave(
        workspace_root=workspace_root,
        project_slug=project_slug,
    )
    language = getattr(project, "language", "zh")
    context = build_questionnaire_design_context(
        project_name=project.name,
        research_goal=payload.research_goal,
        hypotheses=payload.hypotheses,
        knowledge_snippets=snippets,
        brief_background=brief.background if brief else "",
        brief_target_audience=brief.target_audience if brief else "",
        language=language,
        bilingual=bilingual,
    )
    prompt = load_questionnaire_prompt()
    llm_output = client.generate(f"{prompt}\n\n{context}")
    markdown = build_questionnaire_markdown(llm_output=llm_output, citations=snippets)
    return save_questionnaire_draft(
        project_slug=project_slug,
        project_name=project.name,
        payload=payload,
        workspace_root=workspace_root,
        wave_id=current_wave.id if current_wave is not None else None,
        markdown_spec=markdown,
        citations=snippets,
        retrieved_snippets=snippets,
    )


def _build_refinement_prompt(
    *,
    previous_markdown: str,
    feedback: str,
    research_goal: str,
    knowledge_snippets: list[dict],
) -> str:
    sections = [
        load_questionnaire_refine_prompt(),
        "",
        f"Research Goal: {research_goal}",
        "",
        "Current Draft:",
        previous_markdown,
        "",
        "Researcher Feedback:",
        feedback,
    ]
    if knowledge_snippets:
        sections.extend(
            [
                "",
                "Knowledge Context:",
                *[
                    f"- {format_knowledge_item(snippet)}"
                    for snippet in knowledge_snippets
                ],
            ]
        )
    return "\n".join(sections).strip()


def refine_questionnaire_draft(
    *,
    llm_client: LLMClient,
    previous_markdown: str,
    feedback: str,
    research_goal: str,
    knowledge_snippets: list[dict],
    parent_version_id: str | None = None,
) -> QuestionnaireSpecVersion:
    """Generate a refined questionnaire draft based on user feedback."""
    prompt = _build_refinement_prompt(
        previous_markdown=previous_markdown,
        feedback=feedback,
        research_goal=research_goal,
        knowledge_snippets=knowledge_snippets,
    )
    response = llm_client.generate(prompt)

    refined_goal = research_goal
    if feedback:
        refined_goal = f"{research_goal} [refined: {feedback}]"

    if parent_version_id:
        refined_goal = refined_goal

    return QuestionnaireSpecVersion(
        project_slug="",
        wave_id=None,
        version_id=str(uuid4()),
        research_goal=refined_goal,
        markdown_spec=response,
        citations=[],
        retrieved_snippets=knowledge_snippets,
    )
