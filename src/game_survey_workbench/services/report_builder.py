"""Build structured report sections from analysis artifacts."""

from __future__ import annotations

from game_survey_workbench.services.report_sections import (
    ReportSection,
    ReportSectionRegistry,
)


def build_report_sections(
    *,
    brief: dict | None,
    dataset_meta: dict,
    statistical_findings: list[str],
    coded_themes: list[dict],
    insight_narrative: str | None,
    evidence_section: str | None,
    recommendations: list[str],
) -> ReportSectionRegistry:
    """Populate a section registry from available analysis artifacts."""

    registry = ReportSectionRegistry()

    executive_summary = _build_executive_summary(
        insight_narrative=insight_narrative,
        statistical_findings=statistical_findings,
    )
    if executive_summary:
        registry.register(
            ReportSection(
                key="executive_summary",
                title="Executive Summary",
                order=10,
                content=executive_summary,
            )
        )

    registry.register(
        ReportSection(
            key="methodology",
            title="Methodology",
            order=20,
            content=_build_methodology(brief=brief, dataset_meta=dataset_meta),
        )
    )

    if statistical_findings:
        registry.register(
            ReportSection(
                key="statistical_findings",
                title="Statistical Findings",
                order=30,
                content="\n".join(f"- {finding}" for finding in statistical_findings),
            )
        )

    if coded_themes:
        registry.register(
            ReportSection(
                key="qualitative_themes",
                title="Qualitative Themes",
                order=40,
                content=_build_themes_section(coded_themes),
            )
        )

    if insight_narrative:
        registry.register(
            ReportSection(
                key="analysis_narrative",
                title="Analysis",
                order=50,
                content=insight_narrative,
            )
        )

    if recommendations:
        registry.register(
            ReportSection(
                key="recommendations",
                title="Recommendations",
                order=60,
                content="\n".join(f"- {recommendation}" for recommendation in recommendations),
            )
        )

    if evidence_section:
        registry.register(
            ReportSection(
                key="evidence_basis",
                title="Evidence Basis",
                order=90,
                content=evidence_section,
            )
        )

    return registry


def _build_executive_summary(
    *,
    insight_narrative: str | None,
    statistical_findings: list[str],
) -> str:
    if insight_narrative:
        paragraphs = insight_narrative.strip().split("\n\n")
        return paragraphs[0] if paragraphs else ""
    if statistical_findings:
        lines = ["Key findings from this analysis:", ""]
        lines.extend(f"- {finding}" for finding in statistical_findings[:5])
        return "\n".join(lines)
    return ""


def _build_methodology(*, brief: dict | None, dataset_meta: dict) -> str:
    lines: list[str] = []

    if brief:
        background = brief.get("background", "")
        if background:
            lines.append(f"**Research Background:** {background}")
            lines.append("")

        objectives = brief.get("objectives", [])
        if objectives:
            lines.append("**Research Objectives:**")
            lines.extend(f"- {objective}" for objective in objectives)
            lines.append("")

        target_audience = brief.get("target_audience", "")
        if target_audience:
            lines.append(f"**Target Audience:** {target_audience}")
            lines.append("")

    row_count = dataset_meta.get("row_count", 0)
    question_count = dataset_meta.get("question_count", 0)
    question_types = dataset_meta.get("question_types", {})

    lines.append(f"**Sample:** {row_count} respondents, {question_count} questions")
    if question_types:
        parts = [
            f"{count} {question_type.replace('_', ' ')}"
            for question_type, count in question_types.items()
            if count
        ]
        if parts:
            lines.append(f"**Question Types:** {', '.join(parts)}")

    return "\n".join(lines)


def _build_themes_section(coded_themes: list[dict]) -> str:
    lines: list[str] = []

    for theme in coded_themes:
        name = theme.get("theme_name", "Unknown")
        count = theme.get("count", 0)
        examples = theme.get("example_responses", [])

        lines.append(f"**{name}** (n={count})")
        for example in examples[:2]:
            lines.append(f'- _"{example}"_')
        lines.append("")

    return "\n".join(lines)
