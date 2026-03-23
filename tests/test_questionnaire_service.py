import pytest
from pathlib import Path

from game_survey_workbench.errors import (
    NoKnowledgeMatchedError,
    NoKnowledgeSelectedError,
)
from game_survey_workbench.llm.client import FakeLLMClient
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.questionnaire import (
    QuestionnaireDraftRequest,
    QuestionnaireSpecVersion,
)
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.questionnaires import (
    build_questionnaire_design_context,
    build_questionnaire_markdown,
    generate_questionnaire_draft,
    load_questionnaire_prompt,
    save_questionnaire_draft,
)
from game_survey_workbench.services.research_waves import create_research_wave

STAGE2_CLOSEOUT_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "stage2_closeout"


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


def test_save_questionnaire_draft_persists_wave_id(tmp_path: Path):
    create_project(
        ProjectCreate(
            slug="returners",
            name="Returners",
        ),
        workspace_root=tmp_path,
    )
    wave = create_research_wave(
        workspace_root=tmp_path,
        project_slug="returners",
        name="1.1 版本问卷",
    )

    version = save_questionnaire_draft(
        project_slug="returners",
        project_name="Returners",
        payload=QuestionnaireDraftRequest(
            research_goal="Understand why players came back",
        ),
        workspace_root=tmp_path,
        wave_id=wave.id,
        markdown_spec="# Questionnaire Draft",
    )

    assert version.wave_id == wave.id


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
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="returners",
        knowledge_document_ids=[1],
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


def test_generate_questionnaire_draft_rejects_when_no_knowledge_is_selected(tmp_path: Path):
    create_project(
        ProjectCreate(
            slug="empty-project",
            name="Empty Project",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["onboarding"]},
        ),
        workspace_root=tmp_path,
    )

    with pytest.raises(NoKnowledgeSelectedError):
        generate_questionnaire_draft(
            project_slug="empty-project",
            payload=QuestionnaireDraftRequest(research_goal="Study returners"),
            workspace_root=tmp_path,
            client=FakeLLMClient("# Draft"),
        )


def test_generate_questionnaire_draft_rejects_when_selected_knowledge_has_no_hits(tmp_path: Path):
    source = tmp_path / "domain.md"
    source.write_text(
        "---\n"
        "title: Domain Research\n"
        "doc_type: research\n"
        "stage:\n"
        "  - analysis\n"
        "---\n"
        "Domain content only.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)
    create_project(
        ProjectCreate(slug="empty-hit-project", name="Empty Hit Project"),
        workspace_root=tmp_path,
    )
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="empty-hit-project",
        knowledge_document_ids=[1],
    )

    with pytest.raises(NoKnowledgeMatchedError):
        generate_questionnaire_draft(
            project_slug="empty-hit-project",
            payload=QuestionnaireDraftRequest(research_goal="Study returners"),
            workspace_root=tmp_path,
            client=FakeLLMClient("# Draft"),
        )


def test_load_questionnaire_prompt_contains_markdown_instruction():
    prompt = load_questionnaire_prompt()

    assert "Markdown" in prompt


def test_questionnaire_prompt_requests_segmentation_and_rationale():
    prompt = load_questionnaire_prompt()

    assert "segment" in prompt.lower(), (
        "Prompt should request segmentation-aware questions"
    )
    assert "rationale" in prompt.lower() or "why" in prompt.lower(), (
        "Prompt should request question rationale"
    )
    assert "diagnostic" in prompt.lower() or "follow-up" in prompt.lower(), (
        "Prompt should request diagnostic framing"
    )


def test_questionnaire_draft_includes_visible_knowledge_basis_with_realistic_fixture(tmp_path: Path):
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
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="stage2-closeout",
        knowledge_document_ids=[1, 2],
    )

    version = generate_questionnaire_draft(
        project_slug="stage2-closeout",
        payload=QuestionnaireDraftRequest(
            research_goal="Assess whether the season pass experience feels credible enough for repeat play.",
        ),
        workspace_root=tmp_path,
        client=FakeLLMClient(
            "# Questionnaire Draft\n\n## Core Questions\n- Which parts of the reward ladder feel least respectful of player time?"
        ),
    )

    assert "## Knowledge Basis" in version.markdown_spec
    assert "Live Ops Survey Design Guide" in version.markdown_spec
