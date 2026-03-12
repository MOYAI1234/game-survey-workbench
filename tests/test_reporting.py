from game_survey_workbench.services.reporting import render_report_markdown


def test_render_report_markdown_includes_required_sections():
    markdown = render_report_markdown(
        title="Version Satisfaction Report",
        summary_points=["Combat satisfaction is declining."],
        sections={"Key Findings": ["Top box fell among long-term payers."]},
    )

    assert "# Version Satisfaction Report" in markdown
    assert "## Key Findings" in markdown
    assert "Combat satisfaction is declining." in markdown
