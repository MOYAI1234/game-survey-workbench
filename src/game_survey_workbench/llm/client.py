from __future__ import annotations

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
    response_text: str

    def generate(self, prompt: str) -> str:
        return self.response_text


@dataclass
class OpenAICompatibleLLMClient:
    model: str
    api_key: str
    base_url: str

    def generate(self, prompt: str) -> str:
        base_url = self.base_url.rstrip("/")
        timeout = 120.0
        with httpx.Client() as client:
            response = client.post(
                f"{base_url}/responses",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "input": prompt,
                },
                timeout=timeout,
            )

            if response.status_code == 404:
                response = client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=timeout,
                )

        if response.status_code >= 400:
            raise RuntimeError(
                f"OpenAI-compatible request failed with status {response.status_code}."
            )

        payload = response.json()
        choices = payload.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content

        for output in payload.get("output", []):
            for content in output.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return content["text"]

        raise RuntimeError("OpenAI-compatible response did not include output_text.")


def build_llm_client(settings: Settings) -> LLMClient:
    if (
        not settings.llm_provider
        or not settings.llm_model
        or not settings.llm_api_key
        or not settings.llm_base_url
    ):
        raise MissingLLMConfigurationError("LLM runtime is not configured.")

    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleLLMClient(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

    raise MissingLLMConfigurationError(
        f"Unsupported LLM provider: {settings.llm_provider}"
    )
