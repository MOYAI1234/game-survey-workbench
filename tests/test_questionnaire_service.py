from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion
from game_survey_workbench.services.questionnaires import build_questionnaire_design_context


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
