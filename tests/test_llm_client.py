import pytest
import httpx

from game_survey_workbench.config import Settings
from game_survey_workbench.llm.client import (
    MissingLLMConfigurationError,
    OpenAICompatibleLLMClient,
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


def test_openai_compatible_client_posts_prompt_and_returns_text(monkeypatch):
    captured = {}

    def fake_post(self, url, *, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "Generated answer"}
                        ]
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = OpenAICompatibleLLMClient(
        model="demo-model",
        api_key="test-key",
        base_url="https://example.com/v1",
    )

    result = client.generate("Hello")

    assert result == "Generated answer"
    assert captured["url"] == "https://example.com/v1/responses"
    assert captured["json"]["model"] == "demo-model"
