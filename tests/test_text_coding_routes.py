from pathlib import Path

from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.llm.client import OpenAICompatibleLLMClient
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)


def test_code_text_route_returns_themes(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "demo-model")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")

    monkeypatch.setattr(
        OpenAICompatibleLLMClient,
        "generate",
        lambda self, prompt: (
            '{"themes": [{"theme_name": "Boredom", "count": 2, '
            '"example_responses": ["got bored", "nothing to do"]}], "uncoded_count": 1}'
        ),
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
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="churn-study",
        knowledge_document_ids=[1],
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
        f"/projects/churn-study/analysis/{dataset['analysis_run_id']}/code-text",
        json={
            "question_column": "Why did you leave?",
            "responses": ["got bored", "nothing to do", "idk"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["themes"][0]["theme_name"] == "Boredom"
    assert payload["citations"][0]["document_title"] == "Churn Framework"


def test_code_text_route_ignores_client_supplied_responses_and_uses_saved_run_data(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "demo-model")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")

    def fake_generate(self, prompt: str) -> str:
        if "fake client value" in prompt:
            return (
                '{"themes": [{"theme_name": "Client Value", "count": 1, '
                '"example_responses": ["fake client value"]}], "uncoded_count": 0}'
            )
        return (
            '{"themes": [{"theme_name": "Boredom", "count": 2, '
            '"example_responses": ["too hard", "got bored"]}], "uncoded_count": 0}'
        )

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
                    "Why did you leave?,Why did you leave?_other\n"
                    "single_choice,free_text\n"
                    "Other,too hard\n"
                    "Other,got bored\n"
                ),
                "text/csv",
            )
        },
    ).json()

    response = client.post(
        f"/projects/churn-study/analysis/{dataset['analysis_run_id']}/code-text",
        json={
            "question_column": "Why did you leave?",
            "responses": ["fake client value"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["themes"][0]["count"] == 2


def test_code_text_route_returns_500_for_invalid_coding_output(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "demo-model")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "generate", lambda self, prompt: "not-json")

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
                    "Why did you leave?,Why did you leave?_other\n"
                    "single_choice,free_text\n"
                    "Other,too hard\n"
                    "Other,got bored\n"
                ),
                "text/csv",
            )
        },
    ).json()

    response = client.post(
        f"/projects/churn-study/analysis/{dataset['analysis_run_id']}/code-text",
        json={"question_column": "Why did you leave?"},
    )

    assert response.status_code == 500


def test_code_text_route_degrades_without_knowledge(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "demo-model")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")

    monkeypatch.setattr(
        OpenAICompatibleLLMClient,
        "generate",
        lambda self, prompt: (
            '{"themes": [{"theme_name": "Boredom", "count": 2, '
            '"example_responses": ["got bored", "nothing to do"]}], "uncoded_count": 1}'
        ),
    )

    client = TestClient(create_app())
    client.post(
        "/projects",
        json={
            "slug": "no-kb-coding",
            "name": "No KB Coding",
            "knowledge_pack": {"doc_types": ["theory"], "scenarios": ["churn"]},
        },
    )

    dataset = client.post(
        "/projects/no-kb-coding/datasets/import",
        files={
            "file": (
                "dataset.csv",
                "Q1,Why did you leave?\nmetadata,free_text\n1,got bored\n2,nothing to do\n",
                "text/csv",
            )
        },
    ).json()

    response = client.post(
        f"/projects/no-kb-coding/analysis/{dataset['analysis_run_id']}/code-text",
        json={
            "question_column": "Why did you leave?",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["themes"][0]["theme_name"] == "Boredom"
    assert payload["citations"] == []
