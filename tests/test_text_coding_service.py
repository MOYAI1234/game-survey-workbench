from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import get_engine
from game_survey_workbench.llm.client import FakeLLMClient
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.text_coding import CodingResult
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.text_coding import (
    build_coding_context,
    code_open_text_column,
    load_coding_prompt,
    parse_coding_response,
)


def test_coding_result_stores_themes_and_citations():
    result = CodingResult(
        analysis_run_id="run-1",
        question_column="Why did you leave?",
        themes=[
            {"theme_name": "Boredom", "count": 12, "example_responses": ["got bored"]},
        ],
        uncoded_count=3,
        citations=[{"document_title": "Churn Framework", "content": "Boredom is top driver."}],
    )

    assert result.themes[0]["theme_name"] == "Boredom"
    assert result.uncoded_count == 3
    assert result.citations[0]["document_title"] == "Churn Framework"


def test_build_coding_context_includes_responses_and_knowledge():
    context = build_coding_context(
        question="Why did you stop playing?",
        responses=["got bored", "too hard", "no time", "got bored of rewards"],
        knowledge_snippets=[
            {
                "document_title": "Churn Study",
                "content": "Boredom and difficulty are top churn drivers.",
            }
        ],
    )

    assert "Why did you stop playing?" in context
    assert "got bored" in context
    assert "Churn Study" in context


def test_load_coding_prompt_contains_theme_instruction():
    prompt = load_coding_prompt()

    assert "theme" in prompt.lower()


def test_parse_coding_response_extracts_themes():
    raw = (
        '{"themes": [{"theme_name": "Boredom", "count": 2, '
        '"example_responses": ["got bored", "got bored of rewards"]}], '
        '"uncoded_count": 0}'
    )

    result = parse_coding_response(raw)

    assert result["themes"][0]["theme_name"] == "Boredom"
    assert result["uncoded_count"] == 0


def test_code_open_text_column_retrieves_knowledge_and_persists_result(tmp_path: Path):
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

    fake_response = (
        '{"themes": [{"theme_name": "Boredom", "count": 2, '
        '"example_responses": ["got bored", "nothing to do"]}], "uncoded_count": 1}'
    )

    result = code_open_text_column(
        project_slug="churn-study",
        analysis_run_id="run-1",
        question_column="Why did you leave?",
        responses=["got bored", "nothing to do", "idk"],
        workspace_root=tmp_path,
        client=FakeLLMClient(fake_response),
    )

    assert result.themes[0]["theme_name"] == "Boredom"
    assert result.citations[0]["document_title"] == "Churn Framework"

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        saved = session.exec(select(CodingResult)).first()

    assert saved is not None
    assert saved.analysis_run_id == "run-1"
    assert saved.citations[0]["document_title"] == "Churn Framework"
