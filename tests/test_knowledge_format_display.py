from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.services.workspace import bootstrap_workspace


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    return tmp_path


@pytest.fixture()
def app_client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as client:
        yield client


def test_knowledge_page_shows_source_format_badge(app_client, workspace):
    knowledge_dir = workspace / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    pdf_markdown = knowledge_dir / "report.md"
    pdf_markdown.write_text("---\ntitle: From PDF Report\n---\ncontent", encoding="utf-8")
    native_markdown = knowledge_dir / "manual.md"
    native_markdown.write_text("---\ntitle: Native Markdown\n---\ncontent", encoding="utf-8")

    engine = get_engine(workspace)
    with Session(engine) as session:
        session.add(
            KnowledgeDocument(
                source_path=str(pdf_markdown),
                title="From PDF Report",
                source_format="pdf",
            )
        )
        session.add(
            KnowledgeDocument(
                source_path=str(native_markdown),
                title="Native Markdown",
                source_format=None,
            )
        )
        session.commit()

    response = app_client.get("/knowledge")

    html = response.text
    assert 'class="badge">PDF<' in html
    assert "From PDF Report" in html
    assert "Native Markdown" in html
