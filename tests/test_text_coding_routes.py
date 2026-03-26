from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import get_engine
from game_survey_workbench.llm.client import OpenAICompatibleLLMClient
from game_survey_workbench.models.coding_job import CodingBatch, CodingJob
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


def test_code_text_route_uses_dedicated_text_coding_model(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "general-model")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_TEXT_CODING_MODEL", "Qwen/Qwen3.5-35B-A3B")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")

    captured: dict[str, str] = {}

    def fake_generate(self, prompt: str) -> str:
        captured["model"] = self.model
        return (
            '{"themes": [{"theme_name": "Boredom", "count": 2, '
            '"example_responses": ["got bored", "nothing to do"]}], "uncoded_count": 0}'
        )

    monkeypatch.setattr(OpenAICompatibleLLMClient, "generate", fake_generate)

    source = tmp_path / "churn.md"
    source.write_text(
        "---\n"
        "title: Churn Framework\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - analysis\n"
        "---\n"
        "Boredom and difficulty are the top churn drivers.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)

    client = TestClient(create_app())
    client.post(
        "/projects",
        json={
            "slug": "coding-model-test",
            "name": "Coding Model Test",
            "knowledge_pack": {},
        },
    )
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="coding-model-test",
        knowledge_document_ids=[1],
    )

    dataset = client.post(
        "/projects/coding-model-test/datasets/import",
        files={
            "file": (
                "dataset.csv",
                "Q1,Why did you leave?\nmetadata,free_text\n1,got bored\n2,nothing to do\n",
                "text/csv",
            )
        },
    ).json()

    response = client.post(
        f"/projects/coding-model-test/analysis/{dataset['analysis_run_id']}/code-text",
        json={"question_column": "Why did you leave?"},
    )

    assert response.status_code == 201
    assert captured["model"] == "Qwen/Qwen3.5-35B-A3B"


def test_start_code_text_all_route_redirects_immediately(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")

    client = TestClient(create_app())
    client.post(
        "/projects",
        json={"slug": "async-coding", "name": "Async Coding"},
    )
    dataset = client.post(
        "/projects/async-coding/datasets/import",
        files={
            "file": (
                "dataset.csv",
                "Q1,Why did you leave?\nmetadata,free_text\n1,got bored\n2,nothing to do\n",
                "text/csv",
            )
        },
    ).json()

    from game_survey_workbench.routes import text_coding as text_coding_module

    started: dict[str, str] = {}

    def fake_start_background(*, project_slug: str, analysis_run_id: str, workspace_root, **kwargs):
        started["project_slug"] = project_slug
        started["analysis_run_id"] = analysis_run_id
        started["workspace_root"] = str(workspace_root)

    monkeypatch.setattr(
        text_coding_module,
        "start_code_text_all_background",
        fake_start_background,
    )

    response = client.post(
        f"/projects/async-coding/analysis/{dataset['analysis_run_id']}/code-text-all/start",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/projects/async-coding/analysis/latest"
    assert started["project_slug"] == "async-coding"
    assert started["analysis_run_id"] == dataset["analysis_run_id"]


def test_coding_status_route_returns_aggregated_progress(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")

    client = TestClient(create_app())
    client.post(
        "/projects",
        json={"slug": "status-proj", "name": "Status Project"},
    )
    dataset = client.post(
        "/projects/status-proj/datasets/import",
        files={
            "file": (
                "dataset.csv",
                (
                    "Q1_Feedback,Q2_Feedback\n"
                    "free_text,free_text\n"
                    "good,fun\n"
                    "bad,boring\n"
                ),
                "text/csv",
            )
        },
    ).json()

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        job_one = CodingJob(
            project_slug="status-proj",
            analysis_run_id=dataset["analysis_run_id"],
            question_column="Q1_Feedback",
            status="done",
            total_responses=120,
            coded_responses=120,
            batch_size=120,
        )
        job_two = CodingJob(
            project_slug="status-proj",
            analysis_run_id=dataset["analysis_run_id"],
            question_column="Q2_Feedback",
            status="running",
            total_responses=240,
            coded_responses=120,
            batch_size=120,
        )
        session.add(job_one)
        session.add(job_two)
        session.commit()
        session.refresh(job_one)
        session.refresh(job_two)

        session.add(CodingBatch(job_id=job_one.id, batch_index=0, status="done", input_texts_json=["a"]))
        session.add(CodingBatch(job_id=job_two.id, batch_index=0, status="done", input_texts_json=["b"]))
        session.add(CodingBatch(job_id=job_two.id, batch_index=1, status="running", input_texts_json=["c"]))
        session.commit()

    response = client.get(
        f"/projects/status-proj/analysis/{dataset['analysis_run_id']}/coding-status"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["status_text"]
    assert payload["total_questions"] == 2
    assert payload["completed_questions"] == 1
    assert payload["total_batches"] == 3
    assert payload["completed_batches"] == 2
    assert payload["coded_responses"] == 240
    assert payload["total_responses"] == 360
    assert payload["polling"] is True
