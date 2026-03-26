import pytest
import httpx

from game_survey_workbench.config import Settings
from game_survey_workbench.llm.client import (
    MissingLLMConfigurationError,
    OpenAICompatibleLLMClient,
    build_llm_client,
    build_text_coding_client,
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


def test_build_text_coding_client_prefers_dedicated_model_override():
    settings = Settings(
        workspace_root="workspace",
        llm_provider="openai_compatible",
        llm_model="demo-model",
        llm_api_key="test-key",
        llm_base_url="https://example.com/v1",
        text_coding_model="Qwen/Qwen3.5-35B-A3B",
        text_coding_timeout_seconds=120.0,
        text_coding_request_mode="chat_completions",
    )

    client = build_text_coding_client(settings)

    assert isinstance(client, OpenAICompatibleLLMClient)
    assert client.model == "Qwen/Qwen3.5-35B-A3B"
    assert client.timeout == 120.0
    assert client.request_mode == "chat_completions"
    assert client.stream is True
    assert client.extra_body == {
        "enable_thinking": False,
        "response_format": {"type": "json_object"},
        "max_tokens": 5000,
    }


def test_build_text_coding_client_falls_back_to_default_model():
    settings = Settings(
        workspace_root="workspace",
        llm_provider="openai_compatible",
        llm_model="demo-model",
        llm_api_key="test-key",
        llm_base_url="https://example.com/v1",
        text_coding_model=None,
        text_coding_timeout_seconds=120.0,
        text_coding_request_mode="chat_completions",
    )

    client = build_text_coding_client(settings)

    assert isinstance(client, OpenAICompatibleLLMClient)
    assert client.model == "demo-model"
    assert client.timeout == 120.0
    assert client.request_mode == "chat_completions"
    assert client.stream is True


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


def test_openai_compatible_client_falls_back_to_chat_completions_on_responses_404(
    monkeypatch,
):
    attempted_urls = []

    def fake_post(self, url, *, headers=None, json=None, timeout=None):
        attempted_urls.append(url)
        if url.endswith("/responses"):
            return httpx.Response(404, request=httpx.Request("POST", url))
        if url.endswith("/chat/completions"):
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "choices": [
                        {
                            "message": {
                                "content": "Generated from chat completions",
                            }
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = OpenAICompatibleLLMClient(
        model="demo-model",
        api_key="test-key",
        base_url="https://example.com/v1",
    )

    result = client.generate("Hello")

    assert result == "Generated from chat completions"
    assert attempted_urls == [
        "https://example.com/v1/responses",
        "https://example.com/v1/chat/completions",
    ]


def test_openai_compatible_client_uses_extended_timeout_for_provider_requests(
    monkeypatch,
):
    captured_timeouts = []

    def fake_post(self, url, *, headers=None, json=None, timeout=None):
        captured_timeouts.append(timeout)
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
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
    assert len(captured_timeouts) == 1
    assert captured_timeouts[0].connect == 10.0
    assert captured_timeouts[0].read == 600.0
    assert captured_timeouts[0].write == 30.0
    assert captured_timeouts[0].pool == 10.0


def test_build_text_coding_client_uses_90_second_default_timeout():
    settings = Settings(
        workspace_root="workspace",
        llm_provider="openai_compatible",
        llm_model="demo-model",
        llm_api_key="test-key",
        llm_base_url="https://example.com/v1",
    )

    client = build_text_coding_client(settings)

    assert isinstance(client, OpenAICompatibleLLMClient)
    assert client.timeout == 90.0


def test_openai_compatible_client_uses_chat_completions_first_when_requested(
    monkeypatch,
):
    attempted_urls = []

    def fake_post(self, url, *, headers=None, json=None, timeout=None):
        attempted_urls.append(url)
        if url.endswith("/chat/completions"):
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "choices": [
                        {
                            "message": {
                                "content": "Generated from chat first",
                            }
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = OpenAICompatibleLLMClient(
        model="demo-model",
        api_key="test-key",
        base_url="https://example.com/v1",
        timeout=120.0,
        request_mode="chat_completions",
    )

    result = client.generate("Hello")

    assert result == "Generated from chat first"
    assert attempted_urls == ["https://example.com/v1/chat/completions"]


def test_openai_compatible_client_extracts_text_from_chat_content_parts(monkeypatch):
    def fake_post(self, url, *, headers=None, json=None, timeout=None):
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "Generated"},
                                {"type": "text", "text": " answer"},
                            ]
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = OpenAICompatibleLLMClient(
        model="demo-model",
        api_key="test-key",
        base_url="https://example.com/v1",
        request_mode="chat_completions",
    )

    result = client.generate("Hello")

    assert result == "Generated answer"


def test_openai_compatible_client_streams_chat_completion_chunks(monkeypatch):
    captured = {}

    class FakeStreamResponse:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_lines(self):
            yield (
                'data: {"choices":[{"delta":{"content":"","reasoning_content":null,"role":"assistant"}}]}'
            )
            yield 'data: {"choices":[{"delta":{"content":"{\\"themes\\":[","reasoning_content":null}}]}'
            yield 'data: {"choices":[{"delta":{"content":"{\\"theme_name\\":\\"A\\"}","reasoning_content":null}}]}'
            yield 'data: {"choices":[{"delta":{"content":"],\\"uncoded_count\\":0}","reasoning_content":null}}]}'
            yield "data: [DONE]"

    def fake_stream(self, method, url, *, headers=None, json=None, timeout=None):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeStreamResponse()

    monkeypatch.setattr(httpx.Client, "stream", fake_stream)
    client = OpenAICompatibleLLMClient(
        model="demo-model",
        api_key="test-key",
        base_url="https://example.com/v1",
        timeout=90.0,
        request_mode="chat_completions",
        stream=True,
        extra_body={
            "enable_thinking": False,
            "response_format": {"type": "json_object"},
            "max_tokens": 5000,
        },
    )

    result = client.generate("Hello")

    assert result == '{"themes":[{"theme_name":"A"}],"uncoded_count":0}'
    assert captured["method"] == "POST"
    assert captured["url"] == "https://example.com/v1/chat/completions"
    assert captured["json"]["stream"] is True
    assert captured["json"]["enable_thinking"] is False
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["json"]["max_tokens"] == 5000
