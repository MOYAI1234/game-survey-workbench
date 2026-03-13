import pytest

from game_survey_workbench.config import Settings
from game_survey_workbench.llm.client import (
    MissingLLMConfigurationError,
    build_llm_client,
)


def test_build_llm_client_rejects_missing_runtime_configuration():
    settings = Settings(
        workspace_root="workspace",
        llm_provider=None,
        llm_model=None,
        llm_api_key=None,
        llm_base_url=None,
    )

    with pytest.raises(MissingLLMConfigurationError):
        build_llm_client(settings)


def test_build_llm_client_returns_openai_compatible_client():
    settings = Settings(
        workspace_root="workspace",
        llm_provider="openai_compatible",
        llm_model="demo-model",
        llm_api_key="test-key",
        llm_base_url="https://example.com/v1",
    )

    client = build_llm_client(settings)

    assert client.__class__.__name__ == "OpenAICompatibleLLMClient"
