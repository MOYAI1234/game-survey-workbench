from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import get_engine
from game_survey_workbench.llm.client import FakeLLMClient
from game_survey_workbench.models.insight import InsightRecord
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.insights import (
    build_insight_context,
    generate_analysis_insights,
    load_insight_prompt,
    synthesize_insights,
)
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.projects import create_project

STAGE2_CLOSEOUT_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "stage2_closeout"


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


def test_synthesize_insights_keeps_narrative_and_evidence_separate():
    result = synthesize_insights(
        client=FakeLLMClient("Boredom emerged as the dominant churn factor."),
        research_goal="Understand churn drivers",
        statistical_findings=["Top box dropped to 32%"],
        coded_themes=[{"theme_name": "Boredom", "count": 12}],
        knowledge_snippets=[
            {"document_title": "Churn Framework", "content": "Boredom top driver."}
        ],
    )

    assert "## Evidence Basis" not in result.narrative
    assert result.evidence_section.startswith("## Evidence Basis")


def test_load_insight_prompt_contains_citation_instruction():
    prompt = load_insight_prompt()

    assert "citation" in prompt.lower() or "evidence" in prompt.lower()


def test_insight_prompt_requests_executive_takeaway_and_recommendations():
    prompt = load_insight_prompt()

    assert "executive" in prompt.lower() or "takeaway" in prompt.lower(), (
        "Prompt should request an executive takeaway"
    )
    assert "recommend" in prompt.lower() or "action" in prompt.lower(), (
        "Prompt should request actionable recommendations"
    )
    assert "concise" in prompt.lower() or "brief" in prompt.lower(), (
        "Prompt should request concise evidence references"
    )


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

    assert "## Evidence Basis" not in result.narrative
    assert result.citations[0]["document_title"] == "Churn Framework"

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        saved = session.exec(select(InsightRecord)).first()

    assert saved is not None
    assert saved.analysis_run_id == "run-1"
    assert "## Evidence Basis" not in saved.narrative
    assert saved.evidence_section.startswith("## Evidence Basis")


def test_generate_analysis_insights_allows_missing_saved_coding_results(tmp_path: Path):
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
        coded_themes=[],
        workspace_root=tmp_path,
        client=FakeLLMClient("Top box sentiment softened despite a closed-ended questionnaire."),
    )

    assert result.narrative
    assert result.citations[0]["document_title"] == "Churn Framework"


def test_generate_analysis_insights_degrades_when_knowledge_is_missing(tmp_path: Path):
    create_project(
        ProjectCreate(
            slug="empty-project",
            name="Empty Project",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["churn"]},
        ),
        workspace_root=tmp_path,
    )

    result = generate_analysis_insights(
        project_slug="empty-project",
        analysis_run_id="run-1",
        research_goal="Understand churn drivers",
        statistical_findings=["Top box dropped to 32%"],
        coded_themes=[{"theme_name": "Boredom", "count": 12}],
        workspace_root=tmp_path,
        client=FakeLLMClient("Boredom emerged as the dominant churn factor."),
    )

    assert result.narrative
    assert result.citations == []
    assert result.evidence_section == ""


def test_generate_analysis_insights_with_realistic_fixture_persists_visible_evidence(tmp_path: Path):
    for source in (STAGE2_CLOSEOUT_FIXTURE_ROOT / "knowledge").glob("*.md"):
        ingest_knowledge_file(source, project_root=tmp_path)
    create_project(
        ProjectCreate(
            slug="stage2-closeout",
            name="Stage 2 Closeout",
            knowledge_pack={},
        ),
        workspace_root=tmp_path,
    )

    result = generate_analysis_insights(
        project_slug="stage2-closeout",
        analysis_run_id="run-closeout",
        research_goal="Identify the most credible blockers to season pass satisfaction and future conversion.",
        statistical_findings=["Overall satisfaction remains weak in the most dissatisfied segment."],
        coded_themes=[{"theme_name": "Pacing Friction", "count": 2}],
        workspace_root=tmp_path,
        client=FakeLLMClient("Pacing friction and reward clarity dominate season pass concerns."),
    )

    assert result.evidence_section.startswith("## Evidence Basis")
    assert "Live Ops Survey Design Guide" in result.evidence_section or "Free-Text Interpretation Notes" in result.evidence_section
