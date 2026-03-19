from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from game_survey_workbench.app import create_app
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.project_knowledge_selection import (
    ProjectKnowledgeSelection,
)
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    with TestClient(create_app()) as test_client:
        yield test_client


def _ingest_markdown(tmp_path: Path, *, filename: str, title: str, doc_type: str, stage: str) -> None:
    source = tmp_path / filename
    source.write_text(
        "---\n"
        f"title: {title}\n"
        f"doc_type: {doc_type}\n"
        "stage:\n"
        f"  - {stage}\n"
        "---\n\n"
        "知识内容。\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)


def test_project_page_shows_selected_knowledge_and_selection_form(
    client: TestClient,
    tmp_path: Path,
):
    client.post("/projects", json={"slug": "demo", "name": "Demo"})
    _ingest_markdown(
        tmp_path,
        filename="method.md",
        title="方法论文档",
        doc_type="guide",
        stage="design",
    )

    response = client.get("/projects/demo")

    assert response.status_code == 200
    html = response.text
    assert "项目知识选择" in html
    assert 'name="knowledge_document_ids"' in html
    assert "当前已选知识" in html
    assert "方法论文档" in html


def test_project_knowledge_selection_form_replaces_selected_documents(
    client: TestClient,
    tmp_path: Path,
):
    client.post("/projects", json={"slug": "demo", "name": "Demo"})
    _ingest_markdown(
        tmp_path,
        filename="method.md",
        title="方法论文档",
        doc_type="guide",
        stage="design",
    )
    _ingest_markdown(
        tmp_path,
        filename="domain.md",
        title="领域文档",
        doc_type="research",
        stage="analysis",
    )

    response = client.post(
        "/projects/demo/knowledge-selection",
        data={"knowledge_document_ids": ["1", "2"]},
        follow_redirects=False,
    )

    assert response.status_code == 303

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        selected = list(
            session.exec(
                select(ProjectKnowledgeSelection)
                .where(ProjectKnowledgeSelection.project_slug == "demo")
                .order_by(ProjectKnowledgeSelection.id)
            ).all()
        )

    assert [item.knowledge_document_id for item in selected] == [1, 2]
