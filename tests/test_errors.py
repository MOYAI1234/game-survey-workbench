import pytest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from game_survey_workbench.app import create_app
from game_survey_workbench.db import get_engine
from game_survey_workbench.errors import ProjectNotFoundError
from game_survey_workbench.llm.client import FakeLLMClient, OpenAICompatibleLLMClient
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.text_coding import CodingResult
from game_survey_workbench.services.insights import generate_analysis_insights
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.text_coding import code_open_text_column


def test_code_open_text_rejects_missing_project(tmp_path: Path):
    with pytest.raises(ProjectNotFoundError):
        code_open_text_column(
            project_slug="nonexistent",
            analysis_run_id="run-1",
            question_column="Q1",
            responses=["test"],
            workspace_root=tmp_path,
            client=FakeLLMClient("{}"),
        )


def test_generate_insights_degrades_when_knowledge_is_missing(tmp_path: Path):
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

    assert result.citations == []


def test_code_text_route_returns_explicit_error_and_saves_no_result_on_invalid_output(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "demo-model")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setattr(OpenAICompatibleLLMClient, "generate", lambda self, prompt: "not-json")

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

    client = TestClient(create_app())
    client.post(
        "/projects",
        json={
            "slug": "demo",
            "name": "Demo",
            "knowledge_pack": {"doc_types": ["theory"], "scenarios": ["churn"]},
        },
    )
    dataset = client.post(
        "/projects/demo/datasets/import",
        files={
            "file": (
                "survey.csv",
                (
                    "Why did you leave?,Why did you leave?_other\n"
                    "single_choice,free_text\n"
                    "Other,too hard\n"
                    "Other,got bored\n"
                ),
                "text/csv",
            )
        },
    ).json()

    response = client.post(
        f"/projects/demo/analysis/{dataset['analysis_run_id']}/code-text",
        json={"question_column": "Why did you leave?"},
    )

    assert response.status_code == 500
    assert "valid JSON" in response.json()["detail"]

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        assert session.exec(select(CodingResult)).all() == []


def test_generate_insights_route_allows_missing_saved_coding_results(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "demo-model")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setattr(
        OpenAICompatibleLLMClient,
        "generate",
        lambda self, prompt: "Boredom emerged as the dominant churn factor.",
    )

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

    client = TestClient(create_app())
    client.post(
        "/projects",
        json={
            "slug": "demo",
            "name": "Demo",
            "knowledge_pack": {"doc_types": ["theory"], "scenarios": ["churn"]},
        },
    )
    dataset = client.post(
        "/projects/demo/datasets/import",
        files={
            "file": (
                "survey.csv",
                (
                    "Segment,Satisfaction,Why did you leave?,Why did you leave?_other\n"
                    "metadata,scale,single_choice,free_text\n"
                    "A,5,Other,got bored\n"
                    "B,4,Other,nothing to do\n"
                    "C,2,Other,too hard\n"
                ),
                "text/csv",
            )
        },
    ).json()

    response = client.post(
        f"/projects/demo/analysis/{dataset['analysis_run_id']}/insights",
        json={"research_goal": "Understand churn drivers"},
    )

    assert response.status_code == 201
    assert response.json()["narrative"]


def test_brief_route_rejects_missing_project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    client = TestClient(create_app())

    response = client.put(
        "/projects/missing/brief",
        json={"background": "Missing project"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_plan_route_rejects_missing_project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    client = TestClient(create_app())

    response = client.put(
        "/projects/missing/plan",
        json={"tasks": [{"label": "Step A", "status": "pending"}]},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
