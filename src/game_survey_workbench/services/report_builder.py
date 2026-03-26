"""Build business-facing report sections from analysis artifacts."""

from __future__ import annotations

import re

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

_SINGLE_CHOICE_RE = re.compile(
    r"^(?P<question>.+): top choice '(?P<choice>.+)' \((?P<count>\d+) responses, (?P<percentage>[\d.]+)%\)$"
)
_MULTI_SELECT_RE = re.compile(
    r"^(?P<question>.+): most selected item '(?P<choice>.+)' \((?P<count>\d+) selections\)$"
)
_SCALE_RE = re.compile(
    r"^(?P<question>.+): mean (?P<mean>[\d.]+); Top box (?P<top_box>[\d.]+)%$"
)
_KNOWN_TRANSLATIONS = {
    "How much time do you spend in Bravo Bingo each day?": "你每天在 Bravo Bingo 中花多少时间？",
    "We have set 6 bet options in the game. What level do you choose mostly?": "游戏内提供了 6 档下注选项，你平时主要选择哪一档？",
    "To get resources, where do you check most frequently in the game? (Please choose the three places that you checked most frequently)": "为了获取资源，你在游戏里最常查看哪些位置？（请选择你最常查看的三个位置）",
    "1~2 hours": "1~2 小时",
    "Medium Bet (About level 3 to 4)": "中档下注（约 3~4 档）",
    "Daily Check-In": "每日签到",
    "Lack of in-game currency (coins/chips) to play": "缺少游戏内货币（coins/chips）导致无法继续游玩",
    "Poor perceived value or unfair rewards (low bingos, high cost, rigged feeling)": "奖励价值感偏低或公平性不足（低 bingo 回报、高成本、被操控感）",
    "Negative progression or game design issues (fast pace, difficult puzzles, ads)": "成长节奏或玩法设计存在问题（节奏过快、谜题偏难、广告干扰）",
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
    localized_findings = _localize_findings(statistical_findings, language)
    localized_themes = _localize_coded_themes(coded_themes, language)

    executive_summary = _build_executive_summary(
        insight_narrative=insight_narrative,
        statistical_findings=localized_findings,
        coded_themes=localized_themes,
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
        statistical_findings=localized_findings,
        coded_themes=localized_themes,
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

    chart_callouts = _build_chart_callouts(statistical_findings, language)
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
        statistical_findings=localized_findings,
        coded_themes=localized_themes,
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
        coded_themes=localized_themes,
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

    background = str((brief or {}).get("background", "")).strip()
    if background:
        lines.append("")
        lines.append(f"报告背景：{background}")

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


def _build_chart_callouts(statistical_findings: list[str], language: str) -> str:
    if not statistical_findings:
        return ""
    if language != "zh":
        return "\n".join(f"- {finding}" for finding in statistical_findings[:4])

    chart_blocks: list[str] = []
    for index, finding in enumerate(statistical_findings[:3], start=1):
        parsed = _parse_statistical_finding(finding)
        if parsed is None:
            chart_blocks.append(f"图表 {index}\n- {_localize_text(finding, language)}")
            continue

        question = _localize_text(str(parsed["question"]), language)
        if parsed["type"] == "single_choice":
            choice = _localize_text(str(parsed["choice"]), language)
            percentage = float(parsed["percentage"])
            chart_blocks.append(
                "\n".join(
                    [
                        f"图表 {index}：{question}",
                        f"- 最高选择为“{choice}”（{parsed['count']} 人，{percentage:.1f}%）",
                        f"- 占比图：{_build_bar(percentage)} {percentage:.1f}%",
                    ]
                )
            )
            continue
        if parsed["type"] == "multi_select":
            choice = _localize_text(str(parsed["choice"]), language)
            count = int(parsed["count"])
            chart_blocks.append(
                "\n".join(
                    [
                        f"图表 {index}：{question}",
                        f"- 被选择最多的是“{choice}”（{count} 次选择）",
                        f"- 热度图：{_build_bar(min(count / 10, 100.0))} {count} 次",
                    ]
                )
            )
            continue
        if parsed["type"] == "scale":
            mean = float(parsed["mean"])
            top_box = float(parsed["top_box"])
            chart_blocks.append(
                "\n".join(
                    [
                        f"图表 {index}：{question}",
                        f"- 平均分为 {mean:.3f}，Top Box 占比 {top_box:.1f}%",
                        f"- Top Box 图：{_build_bar(top_box)} {top_box:.1f}%",
                    ]
                )
            )
            continue

    return "\n\n".join(chart_blocks)


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

    seen_titles: set[str] = set()
    for line in (evidence_section or "").splitlines():
        title = _extract_reference_title(line)
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        references.append(f"- {title}")

    deduped: list[str] = []
    for item in references:
        if item not in deduped:
            deduped.append(item)

    return "\n".join(deduped)


def _localize_findings(statistical_findings: list[str], language: str) -> list[str]:
    return [_localize_statistical_finding(finding, language) for finding in statistical_findings]


def _localize_coded_themes(coded_themes: list[dict], language: str) -> list[dict]:
    localized: list[dict] = []
    for theme in coded_themes:
        localized.append(
            {
                **theme,
                "theme_name": _localize_text(str(theme.get("theme_name", "未命名主题")), language),
            }
        )
    return localized


def _localize_statistical_finding(finding: str, language: str) -> str:
    if language != "zh":
        return finding

    parsed = _parse_statistical_finding(finding)
    if parsed is None:
        return _localize_text(finding, language)

    question = _localize_text(str(parsed["question"]), language)
    if parsed["type"] == "single_choice":
        choice = _localize_text(str(parsed["choice"]), language)
        return (
            f"{question}：最高选择为“{choice}”"
            f"（{parsed['count']} 人，{float(parsed['percentage']):.1f}%）"
        )
    if parsed["type"] == "multi_select":
        choice = _localize_text(str(parsed["choice"]), language)
        return f"{question}：被选择最多的是“{choice}”（{int(parsed['count'])} 次选择）"
    if parsed["type"] == "scale":
        return (
            f"{question}：平均分为 {float(parsed['mean']):.3f}，"
            f"Top Box 占比 {float(parsed['top_box']):.1f}%"
        )
    return _localize_text(finding, language)


def _parse_statistical_finding(finding: str) -> dict[str, object] | None:
    single_match = _SINGLE_CHOICE_RE.match(finding)
    if single_match:
        return {"type": "single_choice", **single_match.groupdict()}

    multi_match = _MULTI_SELECT_RE.match(finding)
    if multi_match:
        return {"type": "multi_select", **multi_match.groupdict()}

    scale_match = _SCALE_RE.match(finding)
    if scale_match:
        return {"type": "scale", **scale_match.groupdict()}

    return None


def _localize_text(text: str, language: str) -> str:
    if language != "zh":
        return text

    localized = _KNOWN_TRANSLATIONS.get(text.strip())
    if localized:
        return localized
    return text


def _build_bar(value: float) -> str:
    clamped = max(0.0, min(value, 100.0))
    filled = max(1, round(clamped / 5))
    return "█" * filled + "░" * (20 - filled)


def _extract_reference_title(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("## ") or not stripped.startswith("- "):
        return None
    normalized = stripped.removeprefix("- ").strip()
    normalized = normalized.strip("*").strip()
    if ":" in normalized:
        return normalized.split(":", 1)[0].strip() or None
    if "：" in normalized:
        return normalized.split("：", 1)[0].strip() or None
    return normalized or None
