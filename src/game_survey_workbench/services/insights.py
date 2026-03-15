from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.errors import (
    ProjectNotFoundError,
)
from game_survey_workbench.llm.client import LLMClient
from game_survey_workbench.models.insight import InsightRecord
from game_survey_workbench.services.knowledge_ingest import retrieve_project_knowledge
from game_survey_workbench.services.projects import get_project
from game_survey_workbench.services.recommendation import build_recommendation_context
from game_survey_workbench.services.research_brief import get_research_brief


def format_context_item(item: str | dict) -> str:
    if isinstance(item, str):
        return item

    title = item.get("document_title") or item.get("theme_name") or "Unknown Source"
    content = item.get("content", "").strip()
    count = item.get("count")
    details = []
    if count is not None:
        details.append(f"count={count}")
    if content:
        details.append(content)
    detail_text = f" ({'; '.join(details)})" if details else ""
    return f"{title}{detail_text}"


def build_insight_context(
    *,
    research_goal: str,
    statistical_findings: list[str | dict],
    coded_themes: list[str | dict],
    knowledge_snippets: list[str | dict],
    brief_objectives: list[str] | None = None,
    crosstab_findings: list[str | dict] | None = None,
    matrix_findings: list[str | dict] | None = None,
    ranking_findings: list[str | dict] | None = None,
) -> str:
    return build_recommendation_context(
        research_goal=research_goal,
        statistical_findings=[format_context_item(item) for item in statistical_findings],
        crosstab_findings=[format_context_item(item) for item in crosstab_findings or []],
        coded_themes=[format_context_item(item) for item in coded_themes],
        matrix_findings=[format_context_item(item) for item in matrix_findings or []],
        ranking_findings=[format_context_item(item) for item in ranking_findings or []],
        brief_objectives=brief_objectives,
        knowledge_snippets=[format_context_item(item) for item in knowledge_snippets],
    )


def build_evidence_section(*, citations: list[dict]) -> str:
    if not citations:
        return ""
    lines = ["## Evidence Basis"]
    for citation in citations:
        title = citation.get("document_title", "Unknown Source")
        content = citation.get("content", "").strip()
        lines.append(f"- {title}: {content}")
    return "\n".join(lines).strip()


def build_insight_markdown(*, llm_output: str, citations: list[dict]) -> str:
    return llm_output.strip()


def load_insight_prompt() -> str:
    prompt_path = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "insight_synthesis.md"
    return prompt_path.read_text(encoding="utf-8").strip()


@dataclass
class InsightSynthesisResult:
    narrative: str
    evidence_section: str
    citations: list[dict]


def synthesize_insights(
    *,
    client: LLMClient,
    research_goal: str,
    statistical_findings: list[str | dict],
    coded_themes: list[str | dict],
    knowledge_snippets: list[dict],
    brief_objectives: list[str] | None = None,
    crosstab_findings: list[str | dict] | None = None,
    matrix_findings: list[str | dict] | None = None,
    ranking_findings: list[str | dict] | None = None,
) -> InsightSynthesisResult:
    context = build_insight_context(
        research_goal=research_goal,
        statistical_findings=statistical_findings,
        coded_themes=coded_themes,
        knowledge_snippets=knowledge_snippets,
        brief_objectives=brief_objectives,
        crosstab_findings=crosstab_findings,
        matrix_findings=matrix_findings,
        ranking_findings=ranking_findings,
    )
    prompt = load_insight_prompt()
    llm_output = client.generate(f"{prompt}\n\n{context}")
    evidence_section = build_evidence_section(citations=knowledge_snippets)
    narrative = build_insight_markdown(llm_output=llm_output, citations=knowledge_snippets)
    return InsightSynthesisResult(
        narrative=narrative,
        evidence_section=evidence_section,
        citations=knowledge_snippets,
    )


def save_insight_record(*, workspace_root: Path, record: InsightRecord) -> InsightRecord:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def generate_analysis_insights(
    *,
    project_slug: str,
    analysis_run_id: str,
    research_goal: str,
    statistical_findings: list[str | dict],
    coded_themes: list[str | dict],
    workspace_root: Path,
    client: LLMClient,
    top_k: int = 10,
    crosstab_findings: list[str | dict] | None = None,
    matrix_findings: list[str | dict] | None = None,
    ranking_findings: list[str | dict] | None = None,
) -> InsightRecord:
    project = get_project(workspace_root=workspace_root, project_slug=project_slug)
    if project is None:
        raise ProjectNotFoundError("Project not found.")

    snippets = retrieve_project_knowledge(
        workspace_root=workspace_root,
        project_slug=project_slug,
        query=research_goal,
        stages=["analysis"],
        top_k=top_k,
    )
    if not snippets:
        snippets = retrieve_project_knowledge(
            workspace_root=workspace_root,
            project_slug=project_slug,
            query="",
            stages=["analysis"],
            top_k=top_k,
        )

    brief = get_research_brief(
        project_slug=project_slug,
        workspace_root=workspace_root,
    )
    synthesis = synthesize_insights(
        client=client,
        research_goal=research_goal,
        statistical_findings=statistical_findings,
        coded_themes=coded_themes,
        knowledge_snippets=snippets,
        brief_objectives=brief.objectives if brief else None,
        crosstab_findings=crosstab_findings,
        matrix_findings=matrix_findings,
        ranking_findings=ranking_findings,
    )
    record = InsightRecord(
        analysis_run_id=analysis_run_id,
        narrative=synthesis.narrative,
        evidence_section=synthesis.evidence_section,
        citations=synthesis.citations,
    )
    return save_insight_record(workspace_root=workspace_root, record=record)
