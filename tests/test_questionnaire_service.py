import pytest
from pathlib import Path

from game_survey_workbench.llm.client import FakeLLMClient
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.questionnaire import (
    QuestionnaireDraftRequest,
    QuestionnaireSpecVersion,
)
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.questionnaires import (
    build_questionnaire_design_context,
    build_questionnaire_markdown,
    generate_questionnaire_draft,
    load_questionnaire_prompt,
)


def test_questionnaire_spec_version_supports_citations_and_retrieved_snippets():
    version = QuestionnaireSpecVersion(
        project_slug="demo",
        version_id="v1",
        research_goal="Study returners",
        markdown_spec="# Draft",
        citations=[{"document_title": "Retention Framework"}],
        retrieved_snippets=[
            {"content": "Use behavior and attitude questions together."}
        ],
    )

    assert version.citations[0]["document_title"] == "Retention Framework"
    assert (
        version.retrieved_snippets[0]["content"]
        == "Use behavior and attitude questions together."
    )


def test_design_context_uses_project_goal_and_retrieved_knowledge():
    context = build_questionnaire_design_context(
        project_name="Version Satisfaction",
        research_goal="Understand version acceptance drivers",
        hypotheses=["Combat pacing affects satisfaction"],
        knowledge_snippets=["Use behavior + attitude questions together."],
    )

    assert "Version Satisfaction" in context
    assert "Combat pacing affects satisfaction" in context
    assert "Use behavior + attitude questions together." in context


def test_build_questionnaire_design_context_includes_grounding_metadata():
    context = build_questionnaire_design_context(
        project_name="Returners",
        research_goal="Understand why players came back",
        hypotheses=["Return is driven by version updates"],
        knowledge_snippets=[
            {
                "document_title": "Questionnaire Principles",
                "content": "Questions should stay tightly aligned to the research goal.",
                "tags": ["questionnaire"],
            }
        ],
    )

    assert "Questionnaire Principles" in context
    assert "Questions should stay tightly aligned to the research goal." in context


def test_build_questionnaire_markdown_appends_knowledge_basis_section():
    markdown = build_questionnaire_markdown(
        llm_output="# Questionnaire Draft\n\n## Core Questions\n- Why did you return?",
        citations=[
            {
                "document_title": "Questionnaire Principles",
                "content": "Questions should stay tightly aligned to the research goal.",
            }
        ],
    )

    assert "## Knowledge Basis" in markdown
    assert "Questionnaire Principles" in markdown


def test_generate_questionnaire_draft_uses_project_retrieval_and_persists_citations(
    tmp_path: Path,
):
    source = tmp_path / "principles.md"
    source.write_text(
        "---\n"
        "title: Questionnaire Principles\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - design\n"
        "scenario: onboarding\n"
        "---\n"
        "Questions should stay tightly aligned to the research goal.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)
    create_project(
        ProjectCreate(
            slug="returners",
            name="Returners",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["onboarding"]},
        ),
        workspace_root=tmp_path,
    )

    version = generate_questionnaire_draft(
        project_slug="returners",
        payload=QuestionnaireDraftRequest(
            research_goal="Understand why players came back",
            hypotheses=["Return is driven by version updates"],
        ),
        workspace_root=tmp_path,
        client=FakeLLMClient("# Questionnaire Draft\n\n## Core Questions\n- Why did you return?"),
    )

    assert "## Knowledge Basis" in version.markdown_spec
    assert version.citations[0]["document_title"] == "Questionnaire Principles"


def test_generate_questionnaire_draft_rejects_missing_knowledge(tmp_path: Path):
    create_project(
        ProjectCreate(
            slug="empty-project",
            name="Empty Project",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["onboarding"]},
        ),
        workspace_root=tmp_path,
    )

    with pytest.raises(ValueError, match="No knowledge matched"):
        generate_questionnaire_draft(
            project_slug="empty-project",
            payload=QuestionnaireDraftRequest(research_goal="Study returners"),
            workspace_root=tmp_path,
            client=FakeLLMClient("# Draft"),
        )


def test_load_questionnaire_prompt_contains_markdown_instruction():
    prompt = load_questionnaire_prompt()

    assert "Markdown" in prompt
