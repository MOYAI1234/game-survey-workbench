from game_survey_workbench.services.insights import build_insight_context


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
