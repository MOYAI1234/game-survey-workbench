from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    with TestClient(create_app()) as test_client:
        yield test_client


def _ingest_markdown(tmp_path: Path, *, filename: str, content: str) -> None:
    source = tmp_path / filename
    source.write_text(content, encoding="utf-8")
    ingest_knowledge_file(source, project_root=tmp_path)


def test_knowledge_page_shows_global_management_language(client: TestClient):
    response = client.get("/knowledge")

    assert response.status_code == 200
    html = response.text
    assert "共享知识库管理" in html
    assert "筛选知识文档" in html


def test_knowledge_page_upload_form_accepts_pdf_docx_pptx(client: TestClient):
    response = client.get("/knowledge")

    html = response.text
    assert ".pdf" in html
    assert ".docx" in html
    assert ".pptx" in html


def test_knowledge_page_filters_documents_by_stage_and_type(
    client: TestClient,
    tmp_path: Path,
):
    _ingest_markdown(
        tmp_path,
        filename="method-doc.md",
        content=(
            "---\n"
            "title: 方法论文档\n"
            "doc_type: guide\n"
            "stage:\n"
            "  - design\n"
            "tags:\n"
            "  - method\n"
            "---\n\n"
            "方法内容。"
        ),
    )
    _ingest_markdown(
        tmp_path,
        filename="domain-doc.md",
        content=(
            "---\n"
            "title: 领域文档\n"
            "doc_type: research\n"
            "stage:\n"
            "  - analysis\n"
            "tags:\n"
            "  - domain\n"
            "---\n\n"
            "领域内容。"
        ),
    )

    response = client.get("/knowledge?stage=design&doc_type=guide")

    assert response.status_code == 200
    html = response.text
    assert "方法论文档" in html
    assert "领域文档" not in html
