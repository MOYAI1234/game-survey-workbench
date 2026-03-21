import asyncio

import httpx

from game_survey_workbench.retrieval.embeddings import EmbeddingClient


def test_embedding_client_embed_returns_vector():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.read().decode("utf-8")
        assert request.url == "https://example.com/v1/embeddings"
        assert '"model":"text-embedding-3-small"' in payload
        assert '"input":"玩家动机"' in payload
        assert '"dimensions":3' in payload
        return httpx.Response(
            200,
            request=request,
            json={"data": [{"embedding": [0.1, 0.2, 0.3]}]},
        )

    client = EmbeddingClient(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="text-embedding-3-small",
        dimensions=3,
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.embed("玩家动机"))

    assert result == [0.1, 0.2, 0.3]


def test_embedding_client_embed_batch_splits_at_batch_size_boundary():
    batches: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.read().decode("utf-8")
        if '"input":["第一段","第二段"]' in payload:
            batches.append(["第一段", "第二段"])
            embeddings = [[1.0], [2.0]]
        elif '"input":["第三段","第四段"]' in payload:
            batches.append(["第三段", "第四段"])
            embeddings = [[3.0], [4.0]]
        elif '"input":["第五段"]' in payload:
            batches.append(["第五段"])
            embeddings = [[5.0]]
        else:
            raise AssertionError(f"Unexpected payload: {payload}")
        return httpx.Response(
            200,
            request=request,
            json={"data": [{"embedding": item} for item in embeddings]},
        )

    client = EmbeddingClient(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="text-embedding-3-small",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        client.embed_batch(
            ["第一段", "第二段", "第三段", "第四段", "第五段"],
            batch_size=2,
        )
    )

    assert batches == [
        ["第一段", "第二段"],
        ["第三段", "第四段"],
        ["第五段"],
    ]
    assert result == [[1.0], [2.0], [3.0], [4.0], [5.0]]


def test_embedding_client_retries_on_retryable_status_codes():
    attempts = {"count": 0}
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(429, request=request, json={"error": "rate_limited"})
        if attempts["count"] == 2:
            return httpx.Response(500, request=request, json={"error": "temporary"})
        return httpx.Response(
            200,
            request=request,
            json={"data": [{"embedding": [0.9, 0.8]}]},
        )

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    client = EmbeddingClient(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="text-embedding-3-small",
        transport=httpx.MockTransport(handler),
        sleep=fake_sleep,
    )

    result = asyncio.run(client.embed("需要重试"))

    assert result == [0.9, 0.8]
    assert attempts["count"] == 3
    assert sleeps == [1.0, 2.0]
