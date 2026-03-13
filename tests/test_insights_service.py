from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import get_engine
from game_survey_workbench.llm.client import FakeLLMClient
from game_survey_workbench.models.insight import InsightRecord
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.insights import (
    build_insight_context,
    build_insight_markdown,
    generate_analysis_insights,
    load_insight_prompt,
)
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.projects import create_project


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


def test_generate_analysis_insights_retrieves_knowledge_and_persists(tmp_path: Path):
    source = tmp_path / "churn.md"
    source.write_text(
        "---\n"
        "title: Churn Framework\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - analysis\n"
        "scenario: churn\n"
        "---\n"
        "Boredom and difficulty are the top churn drivers.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)
    create_project(
        ProjectCreate(
            slug="churn-study",
            name="Churn Study",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["churn"]},
        ),
        workspace_root=tmp_path,
    )

    result = generate_analysis_insights(
        project_slug="churn-study",
        analysis_run_id="run-1",
        research_goal="Understand churn drivers",
        statistical_findings=["Top box dropped to 32%"],
        coded_themes=[{"theme_name": "Boredom", "count": 12}],
        workspace_root=tmp_path,
        client=FakeLLMClient("Boredom emerged as the dominant churn factor."),
    )

    assert "## Evidence Basis" in result.narrative
    assert result.citations[0]["document_title"] == "Churn Framework"

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        saved = session.exec(select(InsightRecord)).first()

    assert saved is not None
    assert saved.analysis_run_id == "run-1"
    assert "## Evidence Basis" in saved.narrative
