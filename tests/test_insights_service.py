from game_survey_workbench.models.insight import InsightRecord
from game_survey_workbench.services.insights import (
    build_insight_context,
    build_insight_markdown,
    load_insight_prompt,
)


def test_insight_record_stores_narrative_and_structured_citations():
    record = InsightRecord(
        analysis_run_id="run-1",
        narrative="Boredom is the primary churn driver...",
        evidence_section="## Evidence Basis\n- Churn Framework: ...",
        citations=[{"document_title": "Churn Framework", "content": "..."}],
    )

    assert record.citations[0]["document_title"] == "Churn Framework"


def test_build_insight_context_includes_stats_and_knowledge():
    context = build_insight_context(
        research_goal="Evaluate event satisfaction",
        statistical_findings=["Q3 top box dropped to 32%"],
        coded_themes=["Rewards feel too random"],
        knowledge_snippets=["Perceived fairness strongly affects repeat engagement."],
    )

    assert "Q3 top box dropped to 32%" in context
    assert "Rewards feel too random" in context
    assert "Perceived fairness strongly affects repeat engagement." in context


def test_build_insight_context_accepts_dict_knowledge_snippets():
    context = build_insight_context(
        research_goal="Understand churn drivers",
        statistical_findings=["Q3 top box dropped to 32%"],
        coded_themes=[{"theme_name": "Boredom", "count": 12}],
        knowledge_snippets=[
            {"document_title": "Churn Study", "content": "Boredom drives churn."}
        ],
    )

    assert "Churn Study" in context
    assert "Boredom" in context


def test_build_insight_markdown_appends_evidence_section():
    markdown = build_insight_markdown(
        llm_output="Boredom emerged as the dominant churn factor.",
        citations=[
            {"document_title": "Churn Framework", "content": "Boredom top driver."}
        ],
    )

    assert "## Evidence Basis" in markdown
    assert "Churn Framework" in markdown


def test_load_insight_prompt_contains_citation_instruction():
    prompt = load_insight_prompt()

    assert "citation" in prompt.lower() or "evidence" in prompt.lower()
