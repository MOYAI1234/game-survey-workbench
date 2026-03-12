from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str: ...


@dataclass
class FakeLLMClient:
    response_text: str

    def generate(self, prompt: str) -> str:
        return self.response_text
