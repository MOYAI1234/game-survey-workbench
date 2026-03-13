import pytest
from pathlib import Path

from game_survey_workbench.errors import NoKnowledgeMatchedError, ProjectNotFoundError
from game_survey_workbench.llm.client import FakeLLMClient
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.insights import generate_analysis_insights
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


def test_generate_insights_rejects_missing_knowledge(tmp_path: Path):
    create_project(
        ProjectCreate(
            slug="empty-project",
            name="Empty Project",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["churn"]},
        ),
        workspace_root=tmp_path,
    )

    with pytest.raises(NoKnowledgeMatchedError):
        generate_analysis_insights(
            project_slug="empty-project",
            analysis_run_id="run-1",
            research_goal="Understand churn drivers",
            statistical_findings=["Top box dropped to 32%"],
            coded_themes=[{"theme_name": "Boredom", "count": 12}],
            workspace_root=tmp_path,
            client=FakeLLMClient("Boredom emerged as the dominant churn factor."),
        )
