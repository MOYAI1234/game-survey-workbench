from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.llm.client import LLMClient
from game_survey_workbench.models.insight import InsightRecord
from game_survey_workbench.services.knowledge_ingest import retrieve_project_knowledge
from game_survey_workbench.services.projects import get_project


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
) -> str:
    sections = [
        f"Goal: {research_goal}",
        "Stats:",
        *[f"- {format_context_item(item)}" for item in statistical_findings],
        "Themes:",
        *[f"- {format_context_item(item)}" for item in coded_themes],
        "Knowledge:",
        *[f"- {format_context_item(item)}" for item in knowledge_snippets],
    ]
    return "\n".join(sections)


def build_evidence_section(*, citations: list[dict]) -> str:
    lines = ["## Evidence Basis"]
    for citation in citations:
        title = citation.get("document_title", "Unknown Source")
        content = citation.get("content", "").strip()
        lines.append(f"- {title}: {content}")
    return "\n".join(lines).strip()


def build_insight_markdown(*, llm_output: str, citations: list[dict]) -> str:
    return "\n\n".join([llm_output.strip(), build_evidence_section(citations=citations)]).strip()


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
) -> InsightSynthesisResult:
    context = build_insight_context(
        research_goal=research_goal,
        statistical_findings=statistical_findings,
        coded_themes=coded_themes,
        knowledge_snippets=knowledge_snippets,
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
) -> InsightRecord:
    project = get_project(workspace_root=workspace_root, project_slug=project_slug)
    if project is None:
        raise ValueError("Project not found.")

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
    if not snippets:
        raise ValueError("No knowledge matched this insight request.")

    synthesis = synthesize_insights(
        client=client,
        research_goal=research_goal,
        statistical_findings=statistical_findings,
        coded_themes=coded_themes,
        knowledge_snippets=snippets,
    )
    record = InsightRecord(
        analysis_run_id=analysis_run_id,
        narrative=synthesis.narrative,
        evidence_section=synthesis.evidence_section,
        citations=synthesis.citations,
    )
    return save_insight_record(workspace_root=workspace_root, record=record)
