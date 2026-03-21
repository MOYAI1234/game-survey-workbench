from __future__ import annotations

import asyncio
import hashlib
import math
import re
from collections.abc import Awaitable, Callable, Sequence

import httpx

RetrySleep = Callable[[float], Awaitable[None]]


class DeterministicEmbeddingClient:
    def __init__(self, dimensions: int | None = None) -> None:
        self.dimensions = dimensions or 64

    async def embed(self, text: str) -> list[float]:
        return self._embed_text(text)

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        del batch_size
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in self._tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            return vector
        return [value / magnitude for value in vector]

    def _tokenize(self, text: str) -> list[str]:
        lowered = text.lower()
        latin_tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", lowered)
        cjk_tokens = re.findall(r"[\u4e00-\u9fff]", text)
        return latin_tokens + cjk_tokens


class EmbeddingClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        dimensions: int | None = None,
        *,
        timeout: float = 60.0,
        max_attempts: int = 3,
        transport: httpx.BaseTransport | None = None,
        sleep: RetrySleep = asyncio.sleep,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimensions = dimensions
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.transport = transport
        self.sleep = sleep

    async def embed(self, text: str) -> list[float]:
        embeddings = await self._request_embeddings(text)
        if not embeddings:
            raise RuntimeError("Embedding response did not include any vectors.")
        return embeddings[0]

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero.")

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            embeddings.extend(await self._request_embeddings(texts[start : start + batch_size]))
        return embeddings

    async def _request_embeddings(
        self,
        text_or_texts: str | Sequence[str],
    ) -> list[list[float]]:
        payload: dict[str, object] = {
            "model": self.model,
            "input": text_or_texts,
        }
        if self.dimensions is not None:
            payload["dimensions"] = self.dimensions

        headers = {"Authorization": f"Bearer {self.api_key}"}
        attempt = 0
        delay = 1.0
        last_status_code: int | None = None

        while attempt < self.max_attempts:
            attempt += 1
            async with httpx.AsyncClient(transport=self.transport) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )

            if response.status_code < 400:
                data = response.json().get("data", [])
                return [item["embedding"] for item in data]

            last_status_code = response.status_code
            if response.status_code not in {429, 500, 502, 503, 504}:
                break
            if attempt >= self.max_attempts:
                break
            await self.sleep(delay)
            delay *= 2

        raise RuntimeError(
            f"Embedding request failed with status {last_status_code}."
        )
