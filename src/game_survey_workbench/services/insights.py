from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from game_survey_workbench.llm.client import LLMClient


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
