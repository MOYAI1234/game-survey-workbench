from __future__ import annotations


def format_findings_for_recommendation(
    *,
    statistical_findings: list[str] | None = None,
    crosstab_findings: list[str] | None = None,
    coded_themes: list[str] | None = None,
    matrix_findings: list[str] | None = None,
    ranking_findings: list[str] | None = None,
) -> str:
    sections: list[str] = []

    if statistical_findings:
        sections.append("### Statistical Findings")
        sections.extend(f"- {finding}" for finding in statistical_findings)

    if crosstab_findings:
        sections.append("### Cross-tabulation Findings")
        sections.extend(f"- {finding}" for finding in crosstab_findings)

    if matrix_findings:
        sections.append("### Matrix Battery Findings")
        sections.extend(f"- {finding}" for finding in matrix_findings)

    if ranking_findings:
        sections.append("### Ranking Findings")
        sections.extend(f"- {finding}" for finding in ranking_findings)

    if coded_themes:
        sections.append("### Open-text Themes")
        sections.extend(f"- {finding}" for finding in coded_themes)

    return "\n".join(sections)


def build_recommendation_context(
    *,
    research_goal: str,
    statistical_findings: list[str] | None = None,
    crosstab_findings: list[str] | None = None,
    coded_themes: list[str] | None = None,
    matrix_findings: list[str] | None = None,
    ranking_findings: list[str] | None = None,
    brief_objectives: list[str] | None = None,
    knowledge_snippets: list[str] | None = None,
) -> str:
    parts: list[str] = [f"Research Goal: {research_goal}"]

    if brief_objectives:
        parts.append("Research Objectives:")
        parts.extend(f"- {objective}" for objective in brief_objectives)

    findings_text = format_findings_for_recommendation(
        statistical_findings=statistical_findings or [],
        crosstab_findings=crosstab_findings or [],
        coded_themes=coded_themes or [],
        matrix_findings=matrix_findings or [],
        ranking_findings=ranking_findings or [],
    )
    if findings_text:
        parts.append("")
        parts.append("## Evidence Base")
        parts.append(findings_text)

    if knowledge_snippets:
        parts.append("")
        parts.append("## Relevant Knowledge")
        parts.extend(f"- {snippet}" for snippet in knowledge_snippets)

    return "\n".join(parts)
