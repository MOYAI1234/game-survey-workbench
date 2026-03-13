from pathlib import Path

from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.llm.client import OpenAICompatibleLLMClient
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file


def test_generate_insights_route_returns_narrative(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "demo-model")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")

    monkeypatch.setattr(
        OpenAICompatibleLLMClient,
        "generate",
        lambda self, prompt: "Boredom emerged as the dominant churn factor.",
    )

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
            "slug": "churn-study",
            "name": "Churn Study",
            "knowledge_pack": {"doc_types": ["theory"], "scenarios": ["churn"]},
        },
    )

    dataset = client.post(
        "/projects/churn-study/datasets/import",
        files={
            "file": (
                "dataset.csv",
                "Q1,Why did you leave?\nmetadata,free_text\n1,got bored\n2,nothing to do\n3,idk\n",
                "text/csv",
            )
        },
    ).json()

    response = client.post(
        f"/projects/churn-study/analysis/{dataset['analysis_run_id']}/insights",
        json={
            "research_goal": "Understand churn drivers",
            "statistical_findings": ["Top box dropped to 32%"],
            "coded_themes": [{"theme_name": "Boredom", "count": 12}],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert "## Evidence Basis" in payload["narrative"]
    assert payload["citations"][0]["document_title"] == "Churn Framework"
