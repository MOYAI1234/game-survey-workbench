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

    def fake_generate(self, prompt: str) -> str:
        if "Open Text Coding Prompt" in prompt:
            return (
                '{"themes": [{"theme_name": "Boredom", "count": 2, '
                '"example_responses": ["got bored", "nothing to do"]}], "uncoded_count": 0}'
            )
        if "Top box" in prompt or "Boredom" in prompt:
            return "Top box sentiment fell while boredom remained the dominant churn theme."
        return "Generic narrative without saved evidence."

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

    coding = client.post(
        f"/projects/churn-study/analysis/{dataset['analysis_run_id']}/code-text",
        json={"question_column": "Why did you leave?"},
    )

    assert coding.status_code == 201

    response = client.post(
        f"/projects/churn-study/analysis/{dataset['analysis_run_id']}/insights",
        json={"research_goal": "Understand churn drivers"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert "Top box" in payload["narrative"] or "Boredom" in payload["narrative"]
    assert payload["citations"][0]["document_title"] == "Churn Framework"
