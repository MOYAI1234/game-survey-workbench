from pathlib import Path

from fastapi.testclient import TestClient

from game_survey_workbench import app as app_module
from game_survey_workbench.config import get_settings
from game_survey_workbench.retrieval.store import LocalVectorStore


def test_get_settings_reads_embedding_runtime_configuration(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_EMBEDDING_API_KEY", "embed-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_EMBEDDING_BASE_URL", "https://embeddings.example.com/v1")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_EMBEDDING_MODEL", "text-embedding-3-large")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_EMBEDDING_DIMENSIONS", "1024")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_RELEVANCE_THRESHOLD", "0.85")

    settings = get_settings()

    assert settings.workspace_root == tmp_path
    assert settings.llm_provider == "openai_compatible"
    assert settings.llm_model == "gpt-4.1-mini"
    assert settings.llm_api_key == "test-key"
    assert settings.llm_base_url == "https://example.com/v1"
    assert settings.embedding_api_key == "embed-key"
    assert settings.embedding_base_url == "https://embeddings.example.com/v1"
    assert settings.embedding_model == "text-embedding-3-large"
    assert settings.embedding_dimensions == 1024
    assert settings.relevance_threshold == 0.85
    assert settings.chroma_path == tmp_path / "artifacts" / "chroma_db"
    assert settings.legacy_chunks_path == tmp_path / "artifacts" / "vector_store" / "chunks.json"


def test_create_app_initializes_chroma_client_and_ignores_legacy_chunks(
    monkeypatch,
    tmp_path: Path,
):
    legacy_chunks = tmp_path / "artifacts" / "vector_store" / "chunks.json"
    legacy_chunks.parent.mkdir(parents=True, exist_ok=True)
    legacy_chunks.write_text("[]", encoding="utf-8")
    fake_client = object()
    captured: dict[str, Path] = {}

    def fake_build_chroma_client(path: Path):
        captured["path"] = path
        return fake_client

    def fail_load_chunks(self):
        raise AssertionError("legacy chunks.json should not be loaded during startup")

    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(app_module, "_build_chroma_client", fake_build_chroma_client)
    monkeypatch.setattr(LocalVectorStore, "load_chunks", fail_load_chunks)

    with TestClient(app_module.create_app()) as client:
        assert client.app.state.chroma_client is fake_client
        assert client.app.state.settings.chroma_path == tmp_path / "artifacts" / "chroma_db"
        assert captured["path"] == tmp_path / "artifacts" / "chroma_db"
        assert legacy_chunks.exists()
