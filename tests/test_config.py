from game_survey_workbench.config import get_settings


def test_get_settings_reads_llm_runtime_configuration(monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")

    settings = get_settings()

    assert settings.llm_provider == "openai_compatible"
    assert settings.llm_model == "gpt-4.1-mini"
    assert settings.llm_api_key == "test-key"
    assert str(settings.llm_base_url) == "https://example.com/v1"
