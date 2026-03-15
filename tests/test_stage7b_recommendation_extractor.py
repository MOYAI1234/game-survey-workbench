"""Recommendation extraction from insight narrative."""

from game_survey_workbench.services.recommendation_extractor import (
    extract_recommendations,
)


def test_extracts_bullets_under_recommended_actions_heading():
    narrative = (
        "## Executive Summary\n"
        "Players are satisfied overall.\n\n"
        "## Recommended Actions\n"
        "- Reduce gem pack pricing for value-sensitive players\n"
        "- Improve battle pass onboarding messaging\n\n"
        "## Evidence Basis\n"
        "- Pricing complaints appear in open text\n"
    )

    recommendations = extract_recommendations(narrative)

    assert recommendations == [
        "Reduce gem pack pricing for value-sensitive players",
        "Improve battle pass onboarding messaging",
    ]


def test_extracts_numbered_recommendations():
    narrative = (
        "## Recommendations\n"
        "1. Simplify upgrade path for new players\n"
        "2. Test lower first-purchase price point\n"
    )

    recommendations = extract_recommendations(narrative)

    assert recommendations == [
        "Simplify upgrade path for new players",
        "Test lower first-purchase price point",
    ]


def test_returns_empty_list_when_section_missing():
    narrative = "## Executive Summary\nNo explicit recommendations were provided."

    assert extract_recommendations(narrative) == []


def test_ignores_non_bullet_lines_inside_recommendations_section():
    narrative = (
        "## Recommendations\n"
        "The following actions are suggested:\n"
        "- Improve reward clarity\n"
        "Owners: Product + Live Ops\n"
        "- Rebalance early economy pacing\n"
    )

    recommendations = extract_recommendations(narrative)

    assert recommendations == [
        "Improve reward clarity",
        "Rebalance early economy pacing",
    ]
