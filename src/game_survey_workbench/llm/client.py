from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import httpx

from game_survey_workbench.config import Settings


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str: ...


class MissingLLMConfigurationError(RuntimeError):
    pass


@dataclass
class FakeLLMClient:
    response_text: str | None = None

    def generate(self, prompt: str) -> str:
        if self.response_text is not None:
            return self.response_text

        lowered = prompt.lower()
        if "uncoded_count" in lowered or ("themes" in lowered and "json" in lowered):
            return (
                '{"themes": [{"theme_name": "Positive Feedback", "count": 2, '
                '"example_responses": ["Love the graphics", "Good gameplay"]}], '
                '"uncoded_count": 0}'
            )
        if "questionnaire" in lowered or "core questions" in lowered:
            return "# Questionnaire Draft\n\n## Core Questions\n- What motivates players to return?"
        return "Players value the core gameplay but cite friction around ads and stability."


@dataclass
class OpenAICompatibleLLMClient:
    model: str
    api_key: str
    base_url: str
    timeout: float = 600.0
    request_mode: str = "auto"
    stream: bool = False
    extra_body: dict[str, object] | None = None

    def generate(self, prompt: str) -> str:
        base_url = self.base_url.rstrip("/")
        with httpx.Client() as client:
            request_sequence = _build_request_sequence(
                base_url=base_url,
                model=self.model,
                prompt=prompt,
                request_mode=self.request_mode,
                extra_body=self.extra_body,
                stream=self.stream,
            )
            response = None
            for index, request_payload in enumerate(request_sequence):
                if self.stream and _is_chat_completions_request(str(request_payload["url"])):
                    streamed_text = _stream_chat_completion_text(
                        client=client,
                        url=str(request_payload["url"]),
                        api_key=self.api_key,
                        payload=dict(request_payload["json"]),
                        timeout=self.timeout,
                    )
                    if streamed_text.strip():
                        return streamed_text
                    response = httpx.Response(
                        200,
                        request=httpx.Request("POST", str(request_payload["url"])),
                        json={"choices": [{"message": {"content": streamed_text}}]},
                    )
                else:
                    response = client.post(
                        request_payload["url"],
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=request_payload["json"],
                        timeout=_build_timeout(self.timeout),
                    )
                if response.status_code != 404 or index == len(request_sequence) - 1:
                    break

        if response.status_code >= 400:
            raise RuntimeError(
                f"OpenAI-compatible request failed with status {response.status_code}."
            )

        payload = response.json()
        extracted_text = _extract_response_text(payload)
        if extracted_text.strip():
            return extracted_text

        raise RuntimeError("OpenAI-compatible response did not include output_text.")


def _build_request_sequence(
    *,
    base_url: str,
    model: str,
    prompt: str,
    request_mode: str,
    extra_body: dict[str, object] | None = None,
    stream: bool = False,
) -> list[dict[str, object]]:
    responses_request = {
        "url": f"{base_url}/responses",
        "json": {
            "model": model,
            "input": prompt,
            **(extra_body or {}),
        },
    }
    chat_request = {
        "url": f"{base_url}/chat/completions",
        "json": {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            **({"stream": True} if stream else {}),
            **(extra_body or {}),
        },
    }
    if request_mode == "chat_completions":
        return [chat_request, responses_request]
    if request_mode == "responses":
        return [responses_request, chat_request]
    return [responses_request, chat_request]


def _build_timeout(read_timeout: float) -> httpx.Timeout:
    return httpx.Timeout(
        connect=10.0,
        read=read_timeout,
        write=30.0,
        pool=10.0,
    )


def _is_chat_completions_request(url: str) -> bool:
    return url.rstrip("/").endswith("/chat/completions")


def _stream_chat_completion_text(
    *,
    client: httpx.Client,
    url: str,
    api_key: str,
    payload: dict[str, object],
    timeout: float,
) -> str:
    collected_chunks: list[str] = []
    with client.stream(
        "POST",
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=_build_timeout(timeout),
    ) as response:
        if response.status_code >= 400:
            raise RuntimeError(
                f"OpenAI-compatible request failed with status {response.status_code}."
            )
        for line in response.iter_lines():
            if not line:
                continue
            text = line if isinstance(line, str) else line.decode("utf-8", errors="replace")
            if not text.startswith("data: "):
                continue
            data = text[6:].strip()
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            delta = ((chunk.get("choices") or [{}])[0]).get("delta", {})
            collected_chunks.extend(_extract_text_fragments(delta.get("content")))

    return "".join(collected_chunks)


def _extract_response_text(payload: dict[str, object]) -> str:
    choices = payload.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        extracted = "".join(_extract_text_fragments(message.get("content")))
        if extracted.strip():
            return extracted

    for output in payload.get("output", []):
        for content in output.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return str(content["text"])

    return ""


def _extract_text_fragments(content: object) -> list[str]:
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        fragments: list[str] = []
        for item in content:
            if isinstance(item, str):
                fragments.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                fragments.append(text)
        return fragments
    return []


def build_llm_client(settings: Settings, *, model_override: str | None = None) -> LLMClient:
    if settings.llm_provider == "fake":
        return FakeLLMClient()

    effective_model = model_override or settings.llm_model
    if (
        not settings.llm_provider
        or not effective_model
        or not settings.llm_api_key
        or not settings.llm_base_url
    ):
        raise MissingLLMConfigurationError("LLM runtime is not configured.")

    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleLLMClient(
            model=effective_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=600.0,
            request_mode="auto",
        )

    raise MissingLLMConfigurationError(
        f"Unsupported LLM provider: {settings.llm_provider}"
    )


def build_text_coding_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "fake":
        return FakeLLMClient()

    effective_model = settings.text_coding_model or settings.llm_model
    if (
        not settings.llm_provider
        or not effective_model
        or not settings.llm_api_key
        or not settings.llm_base_url
    ):
        raise MissingLLMConfigurationError("LLM runtime is not configured.")

    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleLLMClient(
            model=effective_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.text_coding_timeout_seconds,
            request_mode=settings.text_coding_request_mode,
            stream=True,
            extra_body={
                "enable_thinking": False,
                "response_format": {"type": "json_object"},
                "max_tokens": 5000,
            },
        )

    raise MissingLLMConfigurationError(
        f"Unsupported LLM provider: {settings.llm_provider}"
    )
