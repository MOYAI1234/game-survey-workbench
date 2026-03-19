from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import get_engine
from game_survey_workbench.llm.client import OpenAICompatibleLLMClient
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)
from scripts.run_stage2_closeout_assessment import run_stage2_closeout_assessment


def test_end_to_end_flow_creates_report(client, seeded_workspace, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "demo-model")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")

    def fake_generate(self, prompt: str):
        if "Open Text Coding Prompt" in prompt:
            if "fake client value" in prompt:
                return (
                    '{"themes": [{"theme_name": "Client Value", "count": 1, '
                    '"example_responses": ["fake client value"]}], "uncoded_count": 0}'
                )
            return (
                '{"themes": [{"theme_name": "Boredom", "count": 2, '
                '"example_responses": ["got bored", "nothing to do"]}], "uncoded_count": 1}'
            )
        if "Insight Synthesis Prompt" in prompt:
            if "Client Value" in prompt or "Injected finding" in prompt:
                return "Client-controlled insight should not appear."
            return "Boredom emerged as the dominant churn factor based on the coded themes and knowledge."
        return "# Questionnaire Draft\n\n## Core Questions\n- Why did you return?"

    monkeypatch.setattr(OpenAICompatibleLLMClient, "generate", fake_generate)
    for source in (seeded_workspace / "knowledge").glob("*.md"):
        ingest_knowledge_file(source, project_root=seeded_workspace)

    project = client.post("/projects", json={"slug": "demo", "name": "Demo", "knowledge_pack": {}}).json()
    engine = get_engine(seeded_workspace)
    with Session(engine) as session:
        document_ids = list(
            session.exec(select(KnowledgeDocument.id).order_by(KnowledgeDocument.id)).all()
        )
    replace_project_knowledge_selection(
        workspace_root=seeded_workspace,
        project_slug=project["slug"],
        knowledge_document_ids=document_ids,
    )
    draft = client.post(
        f"/projects/{project['slug']}/questionnaires/draft",
        json={"research_goal": "Learn why players drop after the patch"},
    ).json()
    dataset_file = seeded_workspace / "projects" / "demo" / "data" / "raw" / "dataset.csv"
    dataset = client.post(
        f"/projects/{project['slug']}/datasets/import",
        files={"file": ("dataset.csv", dataset_file.read_text(encoding="utf-8"), "text/csv")},
    ).json()
    coding = client.post(
        f"/projects/{project['slug']}/analysis/{dataset['analysis_run_id']}/code-text",
        json={
            "question_column": "Feel free to tell us what rewards you want to see in the Season Pass! You could also give us more suggestion about the game here!",
            "responses": ["fake client value"],
        },
    ).json()
    insights = client.post(
        f"/projects/{project['slug']}/analysis/{dataset['analysis_run_id']}/insights",
        json={
            "research_goal": "Learn why players drop after the patch",
            "statistical_findings": ["Injected finding"],
            "coded_themes": [{"theme_name": "Client Value", "count": 999}],
        },
    ).json()
    report = client.post(
        f"/projects/{project['slug']}/reports/generate",
        json={"analysis_run_id": dataset["analysis_run_id"]},
    ).json()
    report_path = seeded_workspace / report["path"]
    report_markdown = report_path.read_text(encoding="utf-8")

    assert draft["version_id"]
    assert dataset["dataset_id"]
    assert "标记" not in dataset["question_columns"]
    assert "时间戳记" not in dataset["question_columns"]
    assert dataset["question_columns"]["What are your most satisfying parts of Season Pass?"]["question_type"] == "multi_select"
    assert (
        dataset["question_columns"][
            "Feel free to tell us what rewards you want to see in the Season Pass! You could also give us more suggestion about the game here!"
        ]["question_type"]
        == "free_text"
    )
    assert report["analysis_run_id"] == dataset["analysis_run_id"]
    assert report["path"].endswith(".md")
    assert coding["themes"][0]["theme_name"] == "Boredom"
    assert "Client Value" not in insights["narrative"]
    assert "## Evidence Basis" not in insights["narrative"]
    assert insights["evidence_section"].startswith("## Evidence Basis")
    assert "Churn" in insights["citations"][0]["document_title"] or insights["citations"]
    assert report_markdown.count("## Evidence Basis") == 1
    assert "Boredom emerged as the dominant churn factor" in report_markdown
    assert "Client-controlled insight should not appear." not in report_markdown


def test_stage2_closeout_flow_produces_coding_insight_and_single_report_evidence_section():
    results = run_stage2_closeout_assessment()

    assert Path(results["QUESTIONNAIRE_PATH"]).exists()
    assert results["QUESTIONNAIRE_HAS_KNOWLEDGE_BASIS"] is True
    assert results["CODING_THEMES_PRESENT"] is True
    assert results["INSIGHT_EVIDENCE_PRESENT"] is True
    assert results["REPORT_EVIDENCE_SECTION_COUNT"] == 1
    assert Path(results["REPORT_PATH"]).exists()
