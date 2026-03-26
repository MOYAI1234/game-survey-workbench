"""Report builder populates business-facing report sections from analysis artifacts."""

from game_survey_workbench.services.report_builder import build_report_sections


def test_builder_creates_business_briefing_sections():
    registry = build_report_sections(
        brief={
            "background": "Mobile game player satisfaction study",
            "objectives": [
                "Understand churn drivers",
                "Evaluate monetization perception",
            ],
            "target_audience": "Players with 30+ days tenure",
        },
        dataset_meta={
            "row_count": 500,
            "question_count": 15,
            "question_types": {"single_choice": 8, "free_text": 3, "scale": 4},
        },
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
        insight_narrative="Players remain broadly satisfied, but value perception is weakening among longer-tenure players.",
        evidence_section="## Evidence Basis\n- Churn Framework\n- Monetization Guide",
        recommendations=[
            "Reduce gem pack pricing by 15% to address price sensitivity",
            "Add battle pass for mid-spenders based on segment gap",
        ],
    )

    sections = registry.ordered_sections()
    keys = [section.key for section in sections]
    titles = [section.title for section in sections]

    assert keys == [
        "executive_summary",
        "business_insights",
        "chart_callouts",
        "recommendations",
        "references",
    ]
    assert titles == [
        "一页摘要",
        "核心洞察",
        "关键图表说明",
        "建议动作",
        "参考来源",
    ]


def test_builder_does_not_emit_legacy_research_sections():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 5, "question_types": {}},
        statistical_findings=["Finding 1"],
        coded_themes=[
            {
                "theme_name": "Theme A",
                "count": 5,
                "example_responses": ["example"],
            }
        ],
        insight_narrative="Narrative",
        evidence_section="- Source",
        recommendations=["Action"],
    )

    assert registry.get("methodology") is None
    assert registry.get("statistical_findings") is None
    assert registry.get("qualitative_themes") is None
    assert registry.get("analysis_narrative") is None
    assert registry.get("evidence_basis") is None


def test_builder_creates_executive_summary_from_insight_and_findings():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 200, "question_count": 10, "question_types": {}},
        statistical_findings=["Satisfaction: 4.2/5 mean"],
        coded_themes=[
            {
                "theme_name": "Pricing sensitivity",
                "count": 8,
                "example_responses": ["too expensive"],
            }
        ],
        insight_narrative="Players express high satisfaction but concerns about pricing.",
        evidence_section=None,
        recommendations=[],
    )

    executive_summary = registry.get("executive_summary")

    assert executive_summary is not None
    assert (
        "satisfaction" in executive_summary.content.lower()
        or "pricing" in executive_summary.content.lower()
    )


def test_builder_folds_findings_and_themes_into_business_insights():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 5, "question_types": {}},
        statistical_findings=[
            "Top-box satisfaction fell among long-term payers.",
            "Players in segment A were more likely to report reward frustration.",
        ],
        coded_themes=[
            {
                "theme_name": "Reward frustration",
                "count": 15,
                "example_responses": ["too expensive"],
            }
        ],
        insight_narrative="Long-term value perception is weakening and is beginning to affect retention expectations.",
        evidence_section=None,
        recommendations=[],
    )

    insights = registry.get("business_insights")

    assert insights is not None
    assert "Long-term value perception" in insights.content
    assert "Reward frustration" in insights.content
    assert "统计发现" not in insights.content
    assert "定性主题" not in insights.content


def test_builder_creates_chart_callouts_from_statistical_findings():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 5, "question_types": {}},
        statistical_findings=[
            "Top-box satisfaction dropped from 62% to 48%.",
            "Ad dislike was highest among 14+ day users.",
        ],
        coded_themes=[],
        insight_narrative=None,
        evidence_section=None,
        recommendations=[],
    )

    chart_callouts = registry.get("chart_callouts")

    assert chart_callouts is not None
    assert "Top-box" in chart_callouts.content or "62%" in chart_callouts.content


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


def test_builder_moves_evidence_into_concise_references():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 5, "question_types": {}},
        statistical_findings=[],
        coded_themes=[],
        insight_narrative=None,
        evidence_section="## Evidence Basis\n- **Churn Framework**: retention benchmarks\n- **IAP Guide**: pricing tiers",
        recommendations=[],
    )

    references = registry.get("references")

    assert references is not None
    assert "Churn Framework" in references.content
    assert "Evidence Basis" not in references.content
