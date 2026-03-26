from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlmodel import Session, select

from game_survey_workbench.db import get_engine
from game_survey_workbench.llm.client import FakeLLMClient
from game_survey_workbench.errors import CodingResponseFormatError
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.text_coding import CodingResult
from game_survey_workbench.services.analysis_context import NoFreeTextResponsesFoundError
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.text_coding import (
    build_coding_context,
    code_open_text_column,
    code_open_text_column_with_status,
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


def test_parse_coding_response_raises_typed_error_on_invalid_json():
    with pytest.raises(CodingResponseFormatError):
        parse_coding_response("not-json")


def test_parse_coding_response_extracts_json_from_markdown_code_fence():
    raw = (
        "这里是归纳结果：\n"
        "```json\n"
        '{"themes": [{"theme_name": "Boredom", "count": 2, "example_responses": ["got bored"]}], "uncoded_count": 0}\n'
        "```"
    )

    result = parse_coding_response(raw)

    assert result["themes"][0]["theme_name"] == "Boredom"
    assert result["themes"][0]["count"] == 2


def test_parse_coding_response_extracts_first_json_object_from_explanatory_text():
    raw = (
        "Below is the coding result.\n\n"
        '{"themes": [{"theme_name": "Ads", "count": 3, "example_responses": ["too many ads"]}], "uncoded_count": 1}\n\n'
        "Hope this helps."
    )

    result = parse_coding_response(raw)

    assert result["themes"][0]["theme_name"] == "Ads"
    assert result["uncoded_count"] == 1


def test_parse_coding_response_normalizes_string_numbers_and_single_example_string():
    raw = (
        '{"themes": [{"theme_name": "Rewards", "count": "12", "example_responses": "low rewards"}]}'
    )

    result = parse_coding_response(raw)

    assert result["themes"] == [
        {
            "theme_name": "Rewards",
            "count": 12,
            "example_responses": ["low rewards"],
        }
    ]
    assert result["uncoded_count"] == 0


def test_parse_coding_response_salvages_complete_themes_from_truncated_json():
    raw = (
        '{\n'
        '  "themes": [\n'
        '    {"theme_name": "Coins", "count": 12, "example_responses": ["no coins"]},\n'
        '    {"theme_name": "Ads", "count": 5, "example_responses": ["too many ads"]},\n'
        '    {"theme_name": "Bugs", "count": 2, "example_responses": ["game crashed"]}\n'
        '  ,\n'
        '  "uncoded_count"'
    )

    result = parse_coding_response(raw)

    assert result["themes"] == [
        {
            "theme_name": "Coins",
            "count": 12,
            "example_responses": ["no coins"],
        },
        {
            "theme_name": "Ads",
            "count": 5,
            "example_responses": ["too many ads"],
        },
        {
            "theme_name": "Bugs",
            "count": 2,
            "example_responses": ["game crashed"],
        },
    ]
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
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="churn-study",
        knowledge_document_ids=[1],
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


def test_code_open_text_column_rejects_empty_response_list(tmp_path: Path):
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

    with pytest.raises(NoFreeTextResponsesFoundError):
        code_open_text_column(
            project_slug="churn-study",
            analysis_run_id="run-1",
            question_column="Why did you leave?",
            responses=[],
            workspace_root=tmp_path,
            client=FakeLLMClient('{"themes": [], "uncoded_count": 0}'),
        )

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        assert session.exec(select(CodingResult)).all() == []


def test_code_open_text_column_does_not_persist_invalid_llm_output(tmp_path: Path):
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

    with pytest.raises(CodingResponseFormatError):
        code_open_text_column(
            project_slug="churn-study",
            analysis_run_id="run-1",
            question_column="Why did you leave?",
            responses=["got bored", "nothing to do"],
            workspace_root=tmp_path,
            client=FakeLLMClient("not-json"),
        )

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        assert session.exec(select(CodingResult)).all() == []


def test_code_open_text_column_degrades_when_knowledge_is_missing(tmp_path: Path):
    create_project(
        ProjectCreate(
            slug="empty-project",
            name="Empty Project",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["churn"]},
        ),
        workspace_root=tmp_path,
    )

    result = code_open_text_column(
        project_slug="empty-project",
        analysis_run_id="run-1",
        question_column="Why did you leave?",
        responses=["got bored", "nothing to do"],
        workspace_root=tmp_path,
        client=FakeLLMClient(
            '{"themes": [{"theme_name": "Boredom", "count": 2, "example_responses": ["got bored", "nothing to do"]}], "uncoded_count": 0}'
        ),
    )

    assert result.themes[0]["theme_name"] == "Boredom"
    assert result.citations == []


def test_code_open_text_column_uses_batched_path_for_large_datasets(tmp_path: Path):
    create_project(
        ProjectCreate(
            slug="demo",
            name="Demo",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["churn"]},
        ),
        workspace_root=tmp_path,
    )

    mock_client = MagicMock()
    mock_client.generate.return_value = (
        '{"themes": [{"theme_name": "Positive", "count": 5, "example_responses": ["good"]}], "uncoded_count": 0}'
    )
    responses = [f"response {index}" for index in range(201)]

    result = code_open_text_column(
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        workspace_root=tmp_path,
        client=mock_client,
    )

    assert mock_client.generate.call_count > 1
    assert result.themes


def test_code_open_text_column_uses_single_call_for_small_datasets(tmp_path: Path):
    create_project(
        ProjectCreate(
            slug="demo",
            name="Demo",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["churn"]},
        ),
        workspace_root=tmp_path,
    )

    mock_client = MagicMock()
    mock_client.generate.return_value = (
        '{"themes": [{"theme_name": "Positive", "count": 5, "example_responses": ["good"]}], "uncoded_count": 0}'
    )
    responses = ["response 1", "response 2", "response 3"]

    result = code_open_text_column(
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        workspace_root=tmp_path,
        client=mock_client,
    )

    assert mock_client.generate.call_count == 1
    assert result.themes


def test_code_open_text_column_defaults_to_at_most_20_citations(tmp_path: Path):
    for index in range(25):
        source = tmp_path / f"coding-{index}.md"
        source.write_text(
            "---\n"
            f"title: Coding Theory {index}\n"
            "doc_type: theory\n"
            "stage:\n"
            "  - analysis\n"
            "---\n"
            f"Stress coding note {index}.\n",
            encoding="utf-8",
        )
        ingest_knowledge_file(source, project_root=tmp_path)

    create_project(
        ProjectCreate(
            slug="coding-study",
            name="Coding Study",
            knowledge_pack={},
        ),
        workspace_root=tmp_path,
    )
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="coding-study",
        knowledge_document_ids=list(range(1, 26)),
    )

    result = code_open_text_column(
        project_slug="coding-study",
        analysis_run_id="run-1",
        question_column="What feels stressful?",
        responses=["Resource pressure", "Bankruptcy feels punishing"],
        workspace_root=tmp_path,
        client=FakeLLMClient(
            '{"themes": [{"theme_name": "Pressure", "count": 2, "example_responses": ["Resource pressure", "Bankruptcy feels punishing"]}], "uncoded_count": 0}'
        ),
    )

    assert len(result.citations) == 20


def test_code_open_text_column_with_status_reports_partial_for_failed_batches(tmp_path: Path):
    create_project(
        ProjectCreate(
            slug="demo",
            name="Demo",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["churn"]},
        ),
        workspace_root=tmp_path,
    )

    mock_client = MagicMock()
    mock_client.generate.side_effect = [
        '{"themes": [{"theme_name": "Theme A", "count": 3, "example_responses": ["a"]}], "uncoded_count": 0}',
        Exception("API error"),
        Exception("API error"),
        Exception("API error"),
    ]
    responses = [f"response {index}" for index in range(260)]

    result, execution_status = code_open_text_column_with_status(
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        workspace_root=tmp_path,
        client=mock_client,
    )

    assert execution_status == "partial"
    assert result.themes


def test_code_open_text_column_uses_single_call_when_unique_responses_fit_in_batch(
    tmp_path: Path,
):
    create_project(
        ProjectCreate(
            slug="demo",
            name="Demo",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["churn"]},
        ),
        workspace_root=tmp_path,
    )

    mock_client = MagicMock()
    mock_client.generate.return_value = (
        '{"themes": [{"theme_name": "Positive", "count": 2, "example_responses": ["same response"]}], "uncoded_count": 0}'
    )
    responses = ["same response" for _ in range(200)]

    result, execution_status = code_open_text_column_with_status(
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        workspace_root=tmp_path,
        client=mock_client,
    )

    assert execution_status == "done"
    assert mock_client.generate.call_count == 1
    assert result.themes == [
        {
            "theme_name": "Positive",
            "count": 2,
            "example_responses": ["same response"],
        }
    ]


def test_code_open_text_column_uses_single_call_for_exactly_120_unique_responses(
    tmp_path: Path,
):
    create_project(
        ProjectCreate(
            slug="demo",
            name="Demo",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["churn"]},
        ),
        workspace_root=tmp_path,
    )

    mock_client = MagicMock()
    mock_client.generate.return_value = (
        '{"themes": [{"theme_name": "Positive", "count": 5, "example_responses": ["good"]}], "uncoded_count": 0}'
    )
    responses = [f"response {index}" for index in range(120)]

    result = code_open_text_column(
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        workspace_root=tmp_path,
        client=mock_client,
    )

    assert mock_client.generate.call_count == 1
    assert result.themes


def test_code_open_text_column_uses_batched_path_for_121_unique_responses(
    tmp_path: Path,
):
    create_project(
        ProjectCreate(
            slug="demo",
            name="Demo",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["churn"]},
        ),
        workspace_root=tmp_path,
    )

    mock_client = MagicMock()
    mock_client.generate.return_value = (
        '{"themes": [{"theme_name": "Positive", "count": 5, "example_responses": ["good"]}], "uncoded_count": 0}'
    )
    responses = [f"response {index}" for index in range(121)]

    result = code_open_text_column(
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        workspace_root=tmp_path,
        client=mock_client,
    )

    assert mock_client.generate.call_count > 1
    assert result.themes
