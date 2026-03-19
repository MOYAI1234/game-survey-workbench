from pathlib import Path

from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.llm.client import OpenAICompatibleLLMClient
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)


def test_create_questionnaire_draft_route_returns_grounded_markdown(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "demo-model")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")

    def fake_generate(self, prompt: str):
        return "# Questionnaire Draft\n\n## Core Questions\n- Why did you return?"

    monkeypatch.setattr(
        OpenAICompatibleLLMClient,
        "generate",
        fake_generate,
    )

    source = tmp_path / "principles.md"
    source.write_text(
        "---\n"
        "title: Questionnaire Principles\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - design\n"
        "scenario: onboarding\n"
        "---\n"
        "Questions should stay tightly aligned to the research goal.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)

    client = TestClient(create_app())
    client.post(
        "/projects",
        json={
            "slug": "returners",
            "name": "Returners",
            "knowledge_pack": {"doc_types": ["theory"], "scenarios": ["onboarding"]},
        },
    )
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="returners",
        knowledge_document_ids=[1],
    )

    response = client.post(
        "/projects/returners/questionnaires/draft",
        json={
            "research_goal": "Understand why players came back",
            "hypotheses": ["Return is driven by version updates"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert "## Knowledge Basis" in payload["markdown_spec"]
    assert payload["citations"][0]["document_title"] == "Questionnaire Principles"
