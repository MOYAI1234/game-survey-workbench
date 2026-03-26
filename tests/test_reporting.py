from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from game_survey_workbench.app import create_app
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.dataset import DatasetRecord
from game_survey_workbench.services.dataset_import import import_dataset
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)
from game_survey_workbench.services.reporting import render_report_markdown
from game_survey_workbench.services.workspace import bootstrap_workspace


def test_render_report_markdown_includes_required_sections():
    markdown = render_report_markdown(
        title="Version Satisfaction Report",
        summary_points=["Combat satisfaction is declining."],
        sections={"Key Findings": ["Top box fell among long-term payers."]},
    )

    assert "# Version Satisfaction Report" in markdown
    assert "## Key Findings" in markdown
    assert "Combat satisfaction is declining." in markdown


def test_render_report_markdown_includes_evidence_basis_when_provided():
    markdown = render_report_markdown(
        title="Churn Report",
        summary_points=["Boredom is the top driver."],
        sections={"Key Findings": ["Top box dropped to 32%."]},
        evidence=[
            {"document_title": "Churn Framework", "content": "Boredom top driver."},
        ],
    )

    assert "## Evidence Basis" in markdown
    assert "Churn Framework" in markdown


def test_render_report_markdown_includes_report_date():
    from datetime import date

    markdown = render_report_markdown(
        title="Churn Report",
        summary_points=["Boredom is the top driver."],
        sections={"Key Findings": ["Top box dropped to 32%."]},
    )

    assert "Report generated" in markdown or date.today().isoformat() in markdown


def test_render_report_markdown_evidence_fallback_uses_titles_only_when_content_is_long():
    markdown = render_report_markdown(
        title="Churn Report",
        summary_points=["Summary."],
        sections={},
        evidence=[
            {
                "document_title": "Churn Framework",
                "content": "A" * 300,
            },
        ],
    )

    assert "## Evidence Basis" in markdown
    assert "Churn Framework" in markdown
    assert "A" * 300 not in markdown


def test_render_report_markdown_keeps_single_evidence_basis_section_when_precomposed_section_is_provided():
    markdown = render_report_markdown(
        title="Stage 2 Closeout Report",
        summary_points=["Closeout harness completed."],
        sections={"Key Findings": ["Pacing friction remains visible."]},
        narrative="Players cited pacing friction and weak clarity.",
        evidence=[{"document_title": "Ignored fallback", "content": "Should not duplicate."}],
        evidence_section="## Evidence Basis\n- Live Ops Survey Design Guide: Reward clarity matters.",
    )

    assert markdown.count("## Evidence Basis") == 1
    assert "Live Ops Survey Design Guide" in markdown


def test_generate_report_renders_saved_insight_narrative_without_bullet_wrapping(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "demo-model")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")

    from game_survey_workbench.llm.client import OpenAICompatibleLLMClient

    def fake_generate(self, prompt: str) -> str:
        if "Open Text Coding Prompt" in prompt:
            return (
                '{"themes": [{"theme_name": "Boredom", "count": 2, '
                '"example_responses": ["got bored", "nothing to do"]}], "uncoded_count": 0}'
            )
        return "Boredom emerged as the dominant churn factor."

    monkeypatch.setattr(OpenAICompatibleLLMClient, "generate", fake_generate)

    source = tmp_path / "churn.md"
    source.write_text(
        "---\n"
        "title: Churn Framework\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - analysis\n"
        "scenario: churn\n"
        "---\n"
        "Boredom and difficulty are the top churn drivers.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)

    client = TestClient(create_app())
    client.post(
        "/projects",
        json={
            "slug": "demo",
            "name": "Demo",
            "knowledge_pack": {"doc_types": ["theory"], "scenarios": ["churn"]},
        },
    )
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="demo",
        knowledge_document_ids=[1],
    )
    dataset = client.post(
        "/projects/demo/datasets/import",
        files={
            "file": (
                "survey.csv",
                (
                    "Segment,Satisfaction,Why did you leave?,Why did you leave?_other\n"
                    "metadata,scale,single_choice,free_text\n"
                    "A,5,Other,got bored\n"
                    "B,4,Other,nothing to do\n"
                    "C,2,Other,too hard\n"
                ),
                "text/csv",
            )
        },
    ).json()
    client.post(
        f"/projects/demo/analysis/{dataset['analysis_run_id']}/code-text",
        json={"question_column": "Why did you leave?"},
    )
    client.post(
        f"/projects/demo/analysis/{dataset['analysis_run_id']}/insights",
        json={"research_goal": "Understand churn drivers"},
    )

    report = client.post(
        "/projects/demo/reports/generate",
        json={"analysis_run_id": dataset["analysis_run_id"]},
    ).json()
    report_path = Path(report["path"])
    markdown = report_path.read_text(encoding="utf-8")

    assert "## 一页摘要" in markdown
    assert "## 核心洞察" in markdown
    assert "## 核心洞察\n\nBoredom emerged as the dominant churn factor." in markdown
    assert markdown.count("## 参考来源") == 1


def test_generate_report_rejects_unknown_analysis_run_id(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    client = TestClient(create_app())
    client.post("/projects", json={"slug": "demo", "name": "Demo", "knowledge_pack": {}})

    response = client.post(
        "/projects/demo/reports/generate",
        json={"analysis_run_id": "missing-run"},
    )

    assert response.status_code == 404


def test_save_report_creates_unique_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    bootstrap_workspace(tmp_path)
    project_slug = "demo"
    dataset_path = tmp_path / "survey.csv"
    dataset_path.write_text(
        "Q1,Q2\nsingle_choice,scale\n满意,5\n",
        encoding="utf-8",
    )
    imported = import_dataset(dataset_path, project_slug=project_slug, workspace_root=tmp_path)

    client = TestClient(create_app())
    client.post("/projects", json={"slug": "demo", "name": "Demo", "knowledge_pack": {}})
    first = client.post(
        f"/projects/{project_slug}/reports/generate",
        json={"analysis_run_id": imported.analysis_run_id},
    )
    second = client.post(
        f"/projects/{project_slug}/reports/generate",
        json={"analysis_run_id": imported.analysis_run_id},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["path"] != second.json()["path"]


def test_generate_report_uses_analysis_run_record_for_project_validation(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    bootstrap_workspace(tmp_path)
    dataset_path = tmp_path / "survey.csv"
    dataset_path.write_text(
        "Q1,Q2\nsingle_choice,scale\n满意,5\n",
        encoding="utf-8",
    )
    imported = import_dataset(dataset_path, project_slug="project-a", workspace_root=tmp_path)

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        record = session.exec(
            select(DatasetRecord).where(DatasetRecord.dataset_id == imported.dataset_id)
        ).one()
        record.project_slug = "project-b"
        session.add(record)
        session.commit()

    client = TestClient(create_app())
    client.post("/projects", json={"slug": "project-a", "name": "Project A", "knowledge_pack": {}})
    client.post("/projects", json={"slug": "project-b", "name": "Project B", "knowledge_pack": {}})

    response = client.post(
        "/projects/project-b/reports/generate",
        json={"analysis_run_id": imported.analysis_run_id},
    )

    assert response.status_code == 404


def test_generate_report_succeeds_without_stage_2d_artifacts(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    bootstrap_workspace(tmp_path)
    dataset_path = tmp_path / "survey.csv"
    dataset_path.write_text(
        "Q1,Q2\nsingle_choice,scale\n满意,5\n",
        encoding="utf-8",
    )
    imported = import_dataset(dataset_path, project_slug="demo", workspace_root=tmp_path)

    client = TestClient(create_app())
    client.post("/projects", json={"slug": "demo", "name": "Demo", "knowledge_pack": {}})

    response = client.post(
        "/projects/demo/reports/generate",
        json={"analysis_run_id": imported.analysis_run_id},
    )

    assert response.status_code == 201
    markdown = Path(response.json()["path"]).read_text(encoding="utf-8")
    assert "## 一页摘要" in markdown
    assert "## 核心洞察" in markdown
    assert "## 关键图表说明" in markdown
    assert "## Evidence Basis" not in markdown
