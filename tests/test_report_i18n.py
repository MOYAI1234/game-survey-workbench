from game_survey_workbench.services.report_builder import build_report_sections
from game_survey_workbench.services.report_sections import assemble_report_markdown


def test_report_sections_use_chinese_titles_when_language_is_zh():
    registry = build_report_sections(
        brief={"background": "测试背景", "objectives": ["目标1"], "target_audience": "玩家"},
        dataset_meta={"row_count": 100, "question_count": 10, "question_types": {}},
        statistical_findings=["Finding 1"],
        coded_themes=[],
        insight_narrative="Some narrative",
        evidence_section=None,
        recommendations=["Do X"],
        language="zh",
    )
    sections = registry.ordered_sections()
    titles = [section.title for section in sections]
    assert "一页摘要" in titles
    assert "核心洞察" in titles
    assert "关键图表说明" in titles
    assert "建议动作" in titles
    assert "参考来源" in titles


def test_report_sections_use_english_titles_when_language_is_en():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 50, "question_count": 5, "question_types": {}},
        statistical_findings=["Finding 1"],
        coded_themes=[],
        insight_narrative="Narrative",
        evidence_section=None,
        recommendations=[],
        language="en",
    )
    sections = registry.ordered_sections()
    titles = [section.title for section in sections]
    assert "Executive Summary" in titles
    assert "Business Insights" in titles
    assert "Chart Callouts" in titles
    assert "Recommendations" in titles
    assert "References" in titles


def test_report_sections_default_to_chinese_when_language_omitted():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 10, "question_count": 2, "question_types": {}},
        statistical_findings=["F1"],
        coded_themes=[],
        insight_narrative="N",
        evidence_section=None,
        recommendations=[],
    )
    sections = registry.ordered_sections()
    titles = [section.title for section in sections]
    assert "一页摘要" in titles


def test_assembled_report_markdown_contains_chinese_headings():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 10, "question_types": {}},
        statistical_findings=["Finding 1"],
        coded_themes=[],
        insight_narrative="Narrative text",
        evidence_section=None,
        recommendations=["Action 1"],
        language="zh",
    )
    markdown = assemble_report_markdown(
        title="Demo Report",
        date="2026-03-19",
        registry=registry,
    )
    assert "## 一页摘要" in markdown
    assert "## 核心洞察" in markdown
    assert "## 建议动作" in markdown
