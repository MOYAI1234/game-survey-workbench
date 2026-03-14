from dataclasses import dataclass, field
from pathlib import Path

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.questionnaire import QuestionnaireDraftRequest
from game_survey_workbench.models.research_brief import ResearchBriefPayload
from game_survey_workbench.services.insights import (
    build_insight_context,
    generate_analysis_insights,
)
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.questionnaires import (
    build_questionnaire_design_context,
    generate_questionnaire_draft,
)
from game_survey_workbench.services.research_brief import save_research_brief


@dataclass
class CapturingClient:
    response_text: str
    prompts: list[str] = field(default_factory=list)

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response_text


def test_context_includes_brief_fields():
    context = build_questionnaire_design_context(
        project_name="BP Study",
        research_goal="Measure pass purchase friction",
        hypotheses=["Reward preview is unclear"],
        knowledge_snippets=["Live-ops survey best practices"],
        brief_background="Conversion dropped 12% MoM",
        brief_target_audience="Active L7 >= 3 days, non-payers",
    )

    assert "Conversion dropped 12% MoM" in context
    assert "Active L7 >= 3 days, non-payers" in context


def test_context_works_without_brief():
    context = build_questionnaire_design_context(
        project_name="BP Study",
        research_goal="Measure pass purchase friction",
        hypotheses=["Reward preview is unclear"],
        knowledge_snippets=["Live-ops survey best practices"],
    )

    assert "BP Study" in context
    assert "Measure pass purchase friction" in context


def test_generate_questionnaire_draft_includes_saved_brief_in_prompt(tmp_path: Path):
    source = tmp_path / "design.md"
    source.write_text(
        "---\n"
        "title: Live Ops Survey Design Guide\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - design\n"
        "---\n"
        "Use behavior and attitude questions together.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)
    create_project(
        ProjectCreate(slug="bp-study", name="BP Study", knowledge_pack={}),
        workspace_root=tmp_path,
    )
    save_research_brief(
        project_slug="bp-study",
        payload=ResearchBriefPayload(
            background="Conversion dropped 12% MoM",
            target_audience="Active L7 >= 3 days, non-payers",
        ),
        workspace_root=tmp_path,
    )
    client = CapturingClient("# Questionnaire Draft")

    generate_questionnaire_draft(
        project_slug="bp-study",
        payload=QuestionnaireDraftRequest(
            research_goal="Measure pass purchase friction",
            hypotheses=["Reward preview is unclear"],
        ),
        workspace_root=tmp_path,
        client=client,
    )

    assert client.prompts
    assert "Conversion dropped 12% MoM" in client.prompts[0]
    assert "Active L7 >= 3 days, non-payers" in client.prompts[0]


def test_insight_context_includes_brief_objectives():
    context = build_insight_context(
        research_goal="Understand churn drivers",
        statistical_findings=["Q3 top box dropped to 32%"],
        coded_themes=["Rewards feel too random"],
        knowledge_snippets=["Perceived fairness strongly affects repeat engagement."],
        brief_objectives=[
            "Identify friction points in pass purchase flow",
            "Measure perceived value of pass rewards",
        ],
    )

    assert "Identify friction points in pass purchase flow" in context
    assert "Measure perceived value of pass rewards" in context


def test_insight_context_works_without_brief_objectives():
    context = build_insight_context(
        research_goal="Understand churn drivers",
        statistical_findings=["Q3 top box dropped to 32%"],
        coded_themes=["Rewards feel too random"],
        knowledge_snippets=["Perceived fairness strongly affects repeat engagement."],
    )

    assert "Understand churn drivers" in context
    assert "Rewards feel too random" in context


def test_generate_analysis_insights_includes_saved_brief_objectives_in_prompt(
    tmp_path: Path,
):
    source = tmp_path / "analysis.md"
    source.write_text(
        "---\n"
        "title: Churn Framework\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - analysis\n"
        "---\n"
        "Boredom and difficulty are the top churn drivers.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)
    create_project(
        ProjectCreate(slug="bp-study", name="BP Study", knowledge_pack={}),
        workspace_root=tmp_path,
    )
    save_research_brief(
        project_slug="bp-study",
        payload=ResearchBriefPayload(
            objectives=[
                "Identify friction points in pass purchase flow",
                "Measure perceived value of pass rewards",
            ]
        ),
        workspace_root=tmp_path,
    )
    client = CapturingClient("Boredom emerged as the dominant churn factor.")

    generate_analysis_insights(
        project_slug="bp-study",
        analysis_run_id="run-1",
        research_goal="Understand churn drivers",
        statistical_findings=["Q3 top box dropped to 32%"],
        coded_themes=[{"theme_name": "Boredom", "count": 12}],
        workspace_root=tmp_path,
        client=client,
    )

    assert client.prompts
    assert "Identify friction points in pass purchase flow" in client.prompts[0]
    assert "Measure perceived value of pass rewards" in client.prompts[0]
