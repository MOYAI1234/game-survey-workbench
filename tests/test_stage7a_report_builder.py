"""Report builder populates sections from analysis artifacts."""

from game_survey_workbench.services.report_builder import build_report_sections


def test_builder_creates_methodology_from_brief():
    brief = {
        "background": "Mobile game player satisfaction study",
        "objectives": [
            "Understand churn drivers",
            "Evaluate monetization perception",
        ],
        "target_audience": "Players with 30+ days tenure",
        "hypotheses": ["High spenders are more satisfied"],
    }
    dataset_meta = {
        "row_count": 500,
        "question_count": 15,
        "question_types": {"single_choice": 8, "free_text": 3, "scale": 4},
    }

    registry = build_report_sections(
        brief=brief,
        dataset_meta=dataset_meta,
        statistical_findings=[],
        coded_themes=[],
        insight_narrative=None,
        evidence_section=None,
        recommendations=[],
    )

    methodology = registry.get("methodology")

    assert methodology is not None
    assert "500" in methodology.content
    assert "player satisfaction" in methodology.content.lower()


def test_builder_creates_executive_summary_from_insight():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 200, "question_count": 10, "question_types": {}},
        statistical_findings=["Satisfaction: 4.2/5 mean"],
        coded_themes=[],
        insight_narrative="Players express high satisfaction but concerns about pricing.",
        evidence_section="Source: churn_framework.md",
        recommendations=[],
    )

    executive_summary = registry.get("executive_summary")

    assert executive_summary is not None
    assert (
        "satisfaction" in executive_summary.content.lower()
        or "pricing" in executive_summary.content.lower()
    )


def test_builder_creates_findings_from_deterministic_results():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 5, "question_types": {}},
        statistical_findings=[
            "Satisfaction (scale): mean 4.1, top-2 box 78%",
            "Preferred mode (single_choice): Battle Royale (42%)",
        ],
        coded_themes=[
            {
                "theme_name": "Pricing concerns",
                "count": 15,
                "example_responses": ["too expensive"],
            }
        ],
        insight_narrative=None,
        evidence_section=None,
        recommendations=[],
    )

    findings = registry.get("statistical_findings")
    themes = registry.get("qualitative_themes")

    assert findings is not None
    assert "4.1" in findings.content
    assert themes is not None
    assert "Pricing concerns" in themes.content


def test_builder_creates_recommendations_section():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 5, "question_types": {}},
        statistical_findings=[],
        coded_themes=[],
        insight_narrative=None,
        evidence_section=None,
        recommendations=[
            "Reduce gem pack pricing by 15% to address price sensitivity",
            "Add battle pass for mid-spenders based on segment gap",
        ],
    )

    recommendations = registry.get("recommendations")

    assert recommendations is not None
    assert "gem pack" in recommendations.content.lower()
    assert "battle pass" in recommendations.content.lower()


def test_builder_includes_evidence_basis():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 5, "question_types": {}},
        statistical_findings=[],
        coded_themes=[],
        insight_narrative=None,
        evidence_section="- **Churn Framework**: retention benchmarks\n- **IAP Guide**: pricing tiers",
        recommendations=[],
    )

    evidence = registry.get("evidence_basis")

    assert evidence is not None
    assert "Churn Framework" in evidence.content


def test_builder_strips_duplicate_evidence_heading():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 5, "question_types": {}},
        statistical_findings=[],
        coded_themes=[],
        insight_narrative=None,
        evidence_section="## Evidence Basis\n- **Churn Framework**: retention benchmarks",
        recommendations=[],
    )

    evidence = registry.get("evidence_basis")

    assert evidence is not None
    assert "## Evidence Basis" not in evidence.content


def test_builder_without_brief_skips_methodology_background():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 5, "question_types": {}},
        statistical_findings=["Finding 1"],
        coded_themes=[],
        insight_narrative=None,
        evidence_section=None,
        recommendations=[],
    )

    methodology = registry.get("methodology")

    assert methodology is not None
    assert "100" in methodology.content
    assert "background" not in methodology.content.lower()
