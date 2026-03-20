from pathlib import Path
from unittest.mock import MagicMock

from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.questionnaire import QuestionnaireDraftRequest
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.questionnaires import (
    _language_suffix,
    generate_questionnaire_draft,
)
from game_survey_workbench.services.workspace import bootstrap_workspace


def test_bilingual_suffix_contains_divider_instruction():
    suffix = _language_suffix("zh", bilingual=True)
    assert "---" in suffix
    assert "English" in suffix
    assert "Chinese" in suffix


def test_generate_questionnaire_with_bilingual_flag_includes_bilingual_suffix(
    tmp_path: Path,
):
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    create_project(
        ProjectCreate(slug="demo", name="Demo"),
        workspace_root=tmp_path,
    )

    doc_path = tmp_path / "method.md"
    doc_path.write_text(
        "---\n"
        "title: Method\n"
        "doc_type: guide\n"
        "stage:\n"
        "  - design\n"
        "---\n"
        "Test questionnaire method content.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(doc_path, project_root=tmp_path)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        document = session.exec(select(KnowledgeDocument)).first()
    assert document is not None
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="demo",
        knowledge_document_ids=[document.id],
    )

    mock_client = MagicMock()
    mock_client.generate.return_value = "## English Q\n\n---\n\n## 中文问卷"

    version = generate_questionnaire_draft(
        project_slug="demo",
        payload=QuestionnaireDraftRequest(research_goal="Test"),
        workspace_root=tmp_path,
        client=mock_client,
        bilingual=True,
    )

    assert version.markdown_spec
    prompt = mock_client.generate.call_args[0][0]
    assert "---" in prompt
    assert "English" in prompt
    assert "Chinese" in prompt or "中文" in prompt
