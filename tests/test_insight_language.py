from pathlib import Path
from unittest.mock import MagicMock

from game_survey_workbench.db import create_db_and_tables
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.insights import generate_analysis_insights
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.workspace import bootstrap_workspace


def test_insight_prompt_includes_chinese_language_instruction_for_zh_project(
    tmp_path: Path,
):
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    create_project(
        ProjectCreate(slug="demo", name="Demo", language="zh"),
        workspace_root=tmp_path,
    )

    source = tmp_path / "analysis.md"
    source.write_text(
        "---\n"
        "title: Analysis Method\n"
        "doc_type: guide\n"
        "stage:\n"
        "  - analysis\n"
        "---\n"
        "Player sentiment analysis guidance for Test insights.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="demo",
        knowledge_document_ids=[1],
    )

    client = MagicMock()
    client.generate.return_value = "这是中文洞察。"

    record = generate_analysis_insights(
        project_slug="demo",
        analysis_run_id="run-1",
        research_goal="Test insights",
        statistical_findings=["Top box dropped to 32%"],
        coded_themes=[{"theme_name": "Boredom", "count": 12}],
        workspace_root=tmp_path,
        client=client,
    )

    assert record.narrative == "这是中文洞察。"
    prompt = client.generate.call_args[0][0]
    assert "Chinese" in prompt or "中文" in prompt
