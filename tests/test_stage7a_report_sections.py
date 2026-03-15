"""Report section registry and assembly."""

from game_survey_workbench.services.report_sections import (
    ReportSection,
    ReportSectionRegistry,
    assemble_report_markdown,
)


def test_registry_returns_sections_in_order():
    registry = ReportSectionRegistry()
    registry.register(
        ReportSection(
            key="executive_summary",
            title="Executive Summary",
            order=10,
            content="The study found significant engagement differences.",
        )
    )
    registry.register(
        ReportSection(
            key="methodology",
            title="Methodology",
            order=20,
            content="Online survey, N=500, fielded 2026-03-01 to 2026-03-07.",
        )
    )
    registry.register(
        ReportSection(
            key="findings",
            title="Key Findings",
            order=30,
            content="- Finding 1\n- Finding 2",
        )
    )

    sections = registry.ordered_sections()

    assert [section.key for section in sections] == [
        "executive_summary",
        "methodology",
        "findings",
    ]


def test_assemble_produces_markdown_with_headings():
    registry = ReportSectionRegistry()
    registry.register(
        ReportSection(
            key="exec",
            title="Executive Summary",
            order=10,
            content="Key takeaway here.",
        )
    )
    registry.register(
        ReportSection(
            key="recs",
            title="Recommendations",
            order=20,
            content="- Do X\n- Do Y",
        )
    )

    markdown = assemble_report_markdown(
        title="Player Survey Report",
        date="2026-03-15",
        registry=registry,
    )

    assert "# Player Survey Report" in markdown
    assert "## Executive Summary" in markdown
    assert "Key takeaway here." in markdown
    assert "## Recommendations" in markdown
    assert "- Do X" in markdown


def test_empty_sections_are_skipped():
    registry = ReportSectionRegistry()
    registry.register(
        ReportSection(
            key="exec",
            title="Executive Summary",
            order=10,
            content="Summary here.",
        )
    )
    registry.register(
        ReportSection(
            key="methodology",
            title="Methodology",
            order=20,
            content="",
        )
    )

    markdown = assemble_report_markdown(
        title="Report",
        date="2026-03-15",
        registry=registry,
    )

    assert "## Executive Summary" in markdown
    assert "## Methodology" not in markdown


def test_duplicate_key_replaces_previous():
    registry = ReportSectionRegistry()
    registry.register(
        ReportSection(
            key="exec",
            title="Executive Summary",
            order=10,
            content="First version.",
        )
    )
    registry.register(
        ReportSection(
            key="exec",
            title="Executive Summary",
            order=10,
            content="Updated version.",
        )
    )

    sections = registry.ordered_sections()

    assert len(sections) == 1
    assert sections[0].content == "Updated version."
