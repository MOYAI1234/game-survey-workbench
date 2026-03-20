from game_survey_workbench.services.questionnaires import (
    _language_suffix,
    build_questionnaire_design_context,
)


def test_language_suffix_zh_instructs_chinese_output():
    suffix = _language_suffix("zh")
    assert "中文" in suffix or "Chinese" in suffix


def test_language_suffix_en_instructs_english_output():
    suffix = _language_suffix("en")
    assert "English" in suffix


def test_language_suffix_zh_bilingual_includes_divider_instruction():
    suffix = _language_suffix("zh", bilingual=True)
    assert "---" in suffix
    assert "Chinese" in suffix or "中文" in suffix


def test_build_context_includes_language_instruction():
    context = build_questionnaire_design_context(
        project_name="Demo",
        research_goal="Test",
        hypotheses=[],
        knowledge_snippets=[],
        language="zh",
    )
    assert "中文" in context or "Chinese" in context
