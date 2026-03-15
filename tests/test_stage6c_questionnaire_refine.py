"""Questionnaire iterative refinement with user feedback."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.llm.client import FakeLLMClient
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.questionnaires import refine_questionnaire_draft


def test_refine_includes_previous_draft_in_context():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "# Refined Survey\n\n1. Updated question"

    previous_markdown = "# Original Survey\n\n1. How often do you play?"
    feedback = "Add a question about spending habits"

    result = refine_questionnaire_draft(
        llm_client=mock_llm,
        previous_markdown=previous_markdown,
        feedback=feedback,
        research_goal="understand player behavior",
        knowledge_snippets=[],
    )

    call_args = mock_llm.generate.call_args[0][0]
    assert "How often do you play" in call_args
    assert "spending habits" in call_args
    assert result.markdown_spec is not None


def test_refine_preserves_version_lineage():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "# Refined\n\n1. Q1"

    result = refine_questionnaire_draft(
        llm_client=mock_llm,
        previous_markdown="# Old\n\n1. Q1",
        feedback="improve clarity",
        research_goal="goal",
        knowledge_snippets=[],
        parent_version_id="v-001",
    )

    assert result.research_goal == "goal [refined: improve clarity]"


def test_refine_form_creates_new_questionnaire_version(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    monkeypatch.setattr(
        FakeLLMClient,
        "generate",
        lambda self, prompt: "# Refined Survey\n\n1. How often do you play?\n2. How much do you spend?",
    )

    create_db_and_tables(tmp_path)
    create_project(
        ProjectCreate(
            slug="refine-proj",
            name="Refine Project",
        ),
        workspace_root=tmp_path,
    )
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        session.add(
            QuestionnaireSpecVersion(
                project_slug="refine-proj",
                version_id="v-base",
                research_goal="understand retention",
                markdown_spec="# Survey\n\n1. How often do you play?",
                citations=[],
                retrieved_snippets=[{"document_title": "Guide", "content": "Add spending only if needed."}],
            )
        )
        session.commit()

    with TestClient(create_app()) as client:
        response = client.post(
            "/projects/refine-proj/questionnaires/refine-form",
            data={
                "version_id": "v-base",
                "feedback": "Add a question about spending habits",
            },
            follow_redirects=False,
        )

    with Session(engine) as session:
        versions = list(
            session.exec(
                select(QuestionnaireSpecVersion).where(
                    QuestionnaireSpecVersion.project_slug == "refine-proj"
                )
            ).all()
        )

    assert response.status_code == 303
    assert len(versions) == 2
    latest = sorted(versions, key=lambda item: item.created_at, reverse=True)[0]
    assert "How much do you spend" in latest.markdown_spec
