from game_survey_workbench.models.text_coding import CodingResult
from game_survey_workbench.services.text_coding import (
    build_coding_context,
    load_coding_prompt,
    parse_coding_response,
)


def test_coding_result_stores_themes_and_citations():
    result = CodingResult(
        analysis_run_id="run-1",
        question_column="Why did you leave?",
        themes=[
            {"theme_name": "Boredom", "count": 12, "example_responses": ["got bored"]},
        ],
        uncoded_count=3,
        citations=[{"document_title": "Churn Framework", "content": "Boredom is top driver."}],
    )

    assert result.themes[0]["theme_name"] == "Boredom"
    assert result.uncoded_count == 3
    assert result.citations[0]["document_title"] == "Churn Framework"


def test_build_coding_context_includes_responses_and_knowledge():
    context = build_coding_context(
        question="Why did you stop playing?",
        responses=["got bored", "too hard", "no time", "got bored of rewards"],
        knowledge_snippets=[
            {
                "document_title": "Churn Study",
                "content": "Boredom and difficulty are top churn drivers.",
            }
        ],
    )

    assert "Why did you stop playing?" in context
    assert "got bored" in context
    assert "Churn Study" in context


def test_load_coding_prompt_contains_theme_instruction():
    prompt = load_coding_prompt()

    assert "theme" in prompt.lower()


def test_parse_coding_response_extracts_themes():
    raw = (
        '{"themes": [{"theme_name": "Boredom", "count": 2, '
        '"example_responses": ["got bored", "got bored of rewards"]}], '
        '"uncoded_count": 0}'
    )

    result = parse_coding_response(raw)

    assert result["themes"][0]["theme_name"] == "Boredom"
    assert result["uncoded_count"] == 0
