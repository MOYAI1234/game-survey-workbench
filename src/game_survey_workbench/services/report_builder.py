"""Build business-facing report sections from analysis artifacts."""

from __future__ import annotations

from game_survey_workbench.services.report_sections import (
    ReportSection,
    ReportSectionRegistry,
)

SECTION_TITLES = {
    "zh": {
        "executive_summary": "一页摘要",
        "business_insights": "核心洞察",
        "chart_callouts": "关键图表说明",
        "recommendations": "建议动作",
        "references": "参考来源",
    },
    "en": {
        "executive_summary": "Executive Summary",
        "business_insights": "Business Insights",
        "chart_callouts": "Chart Callouts",
        "recommendations": "Recommendations",
        "references": "References",
    },
}


def _title(key: str, language: str) -> str:
    return SECTION_TITLES.get(language, SECTION_TITLES["zh"]).get(key, key)


def build_report_sections(
    *,
    brief: dict | None,
    dataset_meta: dict,
    statistical_findings: list[str],
    coded_themes: list[dict],
    insight_narrative: str | None,
    evidence_section: str | None,
    recommendations: list[str],
    language: str = "zh",
) -> ReportSectionRegistry:
    """Populate a business-facing section registry from available analysis artifacts."""

    registry = ReportSectionRegistry()

    executive_summary = _build_executive_summary(
        insight_narrative=insight_narrative,
        statistical_findings=statistical_findings,
        coded_themes=coded_themes,
    )
    if executive_summary:
        registry.register(
            ReportSection(
                key="executive_summary",
                title=_title("executive_summary", language),
                order=10,
                content=executive_summary,
            )
        )

    business_insights = _build_business_insights(
        brief=brief,
        statistical_findings=statistical_findings,
        coded_themes=coded_themes,
        insight_narrative=insight_narrative,
    )
    if business_insights:
        registry.register(
            ReportSection(
                key="business_insights",
                title=_title("business_insights", language),
                order=20,
                content=business_insights,
            )
        )

    chart_callouts = _build_chart_callouts(statistical_findings)
    if chart_callouts:
        registry.register(
            ReportSection(
                key="chart_callouts",
                title=_title("chart_callouts", language),
                order=30,
                content=chart_callouts,
            )
        )

    recommendation_lines = _build_recommendations(
        recommendations=recommendations,
        statistical_findings=statistical_findings,
        coded_themes=coded_themes,
    )
    if recommendation_lines:
        registry.register(
            ReportSection(
                key="recommendations",
                title=_title("recommendations", language),
                order=40,
                content="\n".join(f"- {recommendation}" for recommendation in recommendation_lines),
            )
        )

    references = _build_references(
        dataset_meta=dataset_meta,
        coded_themes=coded_themes,
        evidence_section=evidence_section,
    )
    if references:
        registry.register(
            ReportSection(
                key="references",
                title=_title("references", language),
                order=90,
                content=references,
            )
        )

    return registry


def _build_executive_summary(
    *,
    insight_narrative: str | None,
    statistical_findings: list[str],
    coded_themes: list[dict],
) -> str:
    bullets: list[str] = []

    if insight_narrative:
        paragraphs = [part.strip() for part in insight_narrative.split("\n\n") if part.strip()]
        if paragraphs:
            bullets.append(paragraphs[0])

    bullets.extend(statistical_findings[:2])

    for theme in coded_themes[:2]:
        name = str(theme.get("theme_name", "")).strip()
        count = theme.get("count", 0)
        if name:
            bullets.append(f"{name} 是当前开放反馈中的高频主题（{count} 条）。")

    unique_bullets: list[str] = []
    for bullet in bullets:
        cleaned = bullet.strip()
        if cleaned and cleaned not in unique_bullets:
            unique_bullets.append(cleaned)

    return "\n".join(f"- {bullet}" for bullet in unique_bullets[:5])


def _build_business_insights(
    *,
    brief: dict | None,
    statistical_findings: list[str],
    coded_themes: list[dict],
    insight_narrative: str | None,
) -> str:
    lines: list[str] = []

    if insight_narrative:
        lines.append(insight_narrative.strip())

    objectives = brief.get("objectives", []) if brief else []
    if objectives:
        lines.append("")
        lines.append("业务关注点：")
        lines.extend(f"- {objective}" for objective in objectives[:3])

    if statistical_findings:
        lines.append("")
        lines.append("关键支撑信号：")
        lines.extend(f"- {finding}" for finding in statistical_findings[:3])

    if coded_themes:
        lines.append("")
        lines.append("开放反馈中最值得关注的主题：")
        for theme in coded_themes[:3]:
            theme_name = str(theme.get("theme_name", "未命名主题")).strip()
            count = theme.get("count", 0)
            lines.append(f"- {theme_name}（{count} 条）")

    return "\n".join(lines).strip()


def _build_chart_callouts(statistical_findings: list[str]) -> str:
    if not statistical_findings:
        return ""
    return "\n".join(f"- {finding}" for finding in statistical_findings[:4])


def _build_recommendations(
    *,
    recommendations: list[str],
    statistical_findings: list[str],
    coded_themes: list[dict],
) -> list[str]:
    if recommendations:
        return recommendations[:5]

    fallback: list[str] = []
    if statistical_findings:
        fallback.append(f"围绕“{statistical_findings[0]}”对应的问题，优先安排专项优化和后续复盘。")
    if coded_themes:
        fallback.append(
            f"针对开放反馈中的高频主题“{coded_themes[0].get('theme_name', '关键主题')}”，补充定向产品或运营动作。"
        )
    if not fallback:
        fallback.append("基于本次研究结论，整理一页业务复盘并明确下一轮验证重点。")
    return fallback[:5]


def _build_references(
    *,
    dataset_meta: dict,
    coded_themes: list[dict],
    evidence_section: str | None,
) -> str:
    references: list[str] = []

    row_count = dataset_meta.get("row_count")
    question_count = dataset_meta.get("question_count")
    if row_count or question_count:
        references.append(f"- 问卷数据：{row_count or 0} 份答卷，{question_count or 0} 道题。")

    if coded_themes:
        references.append(f"- 开放题编码：共纳入 {len(coded_themes)} 个主题。")

    for line in (evidence_section or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("## "):
            continue
        if not stripped.startswith("- "):
            stripped = f"- {stripped}"
        references.append(stripped)

    deduped: list[str] = []
    for item in references:
        if item not in deduped:
            deduped.append(item)

    return "\n".join(deduped)
