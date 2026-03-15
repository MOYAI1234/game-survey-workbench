from game_survey_workbench.services.recommendation import (
    build_recommendation_context,
    format_findings_for_recommendation,
)


def test_build_recommendation_context_includes_all_signal_types():
    context = build_recommendation_context(
        research_goal="Evaluate event satisfaction",
        statistical_findings=["Q3 top box dropped to 32%"],
        crosstab_findings=["Satisfaction by Segment: Whales 85%, Minnows 40%"],
        coded_themes=["Rewards feel too random (n=12)"],
        matrix_findings=["Q5 battery: Graphics leads, Sound trails by 1.2"],
        brief_objectives=["Identify friction points", "Measure perceived value"],
    )
    assert "Q3 top box dropped to 32%" in context
    assert "Whales 85%" in context
    assert "Rewards feel too random" in context
    assert "Graphics leads" in context
    assert "Identify friction points" in context


def test_format_findings_groups_by_type():
    formatted = format_findings_for_recommendation(
        statistical_findings=["Mean 3.5"],
        crosstab_findings=["Payer vs Free gap: 1.2"],
        coded_themes=["Pacing concern (n=8)"],
    )
    assert "Statistical Findings" in formatted
    assert "Cross-tabulation" in formatted
    assert "Open-text Themes" in formatted


def test_recommendation_context_works_without_optional_fields():
    context = build_recommendation_context(
        research_goal="Basic study",
        statistical_findings=["Mean 4.0"],
    )
    assert "Basic study" in context
    assert "Mean 4.0" in context
