from pathlib import Path

from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.knowledge_feedback import (
    KnowledgeFeedbackPayload,
    save_report_findings_as_knowledge,
)
from game_survey_workbench.services.knowledge_parser import parse_markdown_document
from game_survey_workbench.services.projects import create_project


def test_save_findings_creates_knowledge_file(tmp_path: Path):
    create_project(
        ProjectCreate(slug="bp-study", name="BP Study"),
        workspace_root=tmp_path,
    )
    payload = KnowledgeFeedbackPayload(
        project_slug="bp-study",
        title="BP Study Key Findings",
        key_findings=[
            "Pass conversion dropped 12% among mid-tier payers",
            "Reward preview clarity was the top coded complaint",
        ],
        recommendations=[
            "Add value comparison tooltip on pass purchase screen",
        ],
        source_report_path="reports/report-2026-03-15.md",
    )
    result = save_report_findings_as_knowledge(
        payload=payload,
        workspace_root=tmp_path,
    )
    assert result.file_path.exists()
    assert result.file_path.suffix == ".md"

    content = result.file_path.read_text(encoding="utf-8")
    doc = parse_markdown_document(content)
    assert doc.doc_type == "experience"
    assert "analysis" in doc.stages
    assert "BP Study" in doc.title or "BP Study" in doc.body
    assert "12%" in doc.body


def test_saved_knowledge_includes_source_reference(tmp_path: Path):
    create_project(
        ProjectCreate(slug="bp-study", name="BP Study"),
        workspace_root=tmp_path,
    )
    payload = KnowledgeFeedbackPayload(
        project_slug="bp-study",
        title="BP Study Learnings",
        key_findings=["Finding A"],
        source_report_path="reports/report-2026-03-15.md",
    )
    result = save_report_findings_as_knowledge(
        payload=payload,
        workspace_root=tmp_path,
    )
    content = result.file_path.read_text(encoding="utf-8")
    assert "report-2026-03-15" in content


def test_feedback_without_recommendations(tmp_path: Path):
    create_project(
        ProjectCreate(slug="bp-study", name="BP Study"),
        workspace_root=tmp_path,
    )
    payload = KnowledgeFeedbackPayload(
        project_slug="bp-study",
        title="Minimal Feedback",
        key_findings=["One finding"],
    )
    result = save_report_findings_as_knowledge(
        payload=payload,
        workspace_root=tmp_path,
    )
    assert result.file_path.exists()


def test_feedback_route_returns_saved_file_path(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    client = TestClient(create_app())
    client.post("/projects", json={"slug": "bp-study", "name": "BP Study", "knowledge_pack": {}})

    response = client.post(
        "/reports/feedback-to-knowledge",
        json={
            "project_slug": "bp-study",
            "title": "BP Study Learnings",
            "key_findings": ["Finding A"],
            "recommendations": ["Action A"],
            "source_report_path": "reports/report-2026-03-15.md",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_title"] == "BP Study Learnings"
    assert Path(payload["file_path"]).exists()
