from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

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
        raise NotImplementedError


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
