from __future__ import annotations

from dataclasses import dataclass

from game_survey_workbench.llm.client import LLMClient


def build_insight_context(
    *,
    research_goal: str,
    statistical_findings: list[str],
    coded_themes: list[str],
    knowledge_snippets: list[str],
) -> str:
    sections = [
        f"Goal: {research_goal}",
        "Stats:",
        *[f"- {item}" for item in statistical_findings],
        "Themes:",
        *[f"- {item}" for item in coded_themes],
        "Knowledge:",
        *[f"- {item}" for item in knowledge_snippets],
    ]
    return "\n".join(sections)


@dataclass
class InsightSynthesisResult:
    narrative: str
    citations: list[str]


def synthesize_insights(
    *,
    client: LLMClient,
    research_goal: str,
    statistical_findings: list[str],
    coded_themes: list[str],
    knowledge_snippets: list[str],
) -> InsightSynthesisResult:
    context = build_insight_context(
        research_goal=research_goal,
        statistical_findings=statistical_findings,
        coded_themes=coded_themes,
        knowledge_snippets=knowledge_snippets,
    )
    narrative = client.generate(context)
    return InsightSynthesisResult(
        narrative=narrative,
        citations=knowledge_snippets,
    )
