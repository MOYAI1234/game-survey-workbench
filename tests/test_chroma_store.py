import inspect
import math

from game_survey_workbench.retrieval.chunking import ChunkResult
from game_survey_workbench.retrieval.store import ChromaVectorStore, LocalVectorStore


class FakeEmbeddingClient:
    async def embed(self, text: str) -> list[float]:
        return self._embed_value(text)

    async def embed_batch(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        return [self._embed_value(text) for text in texts]

    def _embed_value(self, text: str) -> list[float]:
        if "玩家动机" in text or "成长感" in text:
            return [0.0]
        if "留存" in text or "回流" in text:
            return [1.0]
        if "定价" in text or "价格" in text:
            return [5.0]
        return [10.0]


class FakeCollection:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def add(
        self,
        *,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        for record_id, document, embedding, metadata in zip(
            ids, documents, embeddings, metadatas, strict=True
        ):
            self.records.append(
                {
                    "id": record_id,
                    "document": document,
                    "embedding": embedding,
                    "metadata": metadata,
                }
            )

    def query(
        self,
        *,
        query_embeddings: list[list[float]],
        where: dict | None = None,
        n_results: int = 10,
    ) -> dict:
        query_embedding = query_embeddings[0]
        matched = [
            record
            for record in self.records
            if _matches_where(record["metadata"], where)
        ]
        matched.sort(
            key=lambda record: math.dist(record["embedding"], query_embedding)
        )
        selected = matched[:n_results]
        return {
            "ids": [[record["id"] for record in selected]],
            "documents": [[record["document"] for record in selected]],
            "metadatas": [[record["metadata"] for record in selected]],
            "distances": [[math.dist(record["embedding"], query_embedding) for record in selected]],
        }

    def delete(self, *, where: dict) -> None:
        self.records = [
            record
            for record in self.records
            if not _matches_where(record["metadata"], where)
        ]


def _matches_where(metadata: dict, where: dict | None) -> bool:
    if not where:
        return True
    if "$and" in where:
        return all(_matches_where(metadata, clause) for clause in where["$and"])
    if "$or" in where:
        return any(_matches_where(metadata, clause) for clause in where["$or"])

    for field, condition in where.items():
        value = metadata.get(field)
        if isinstance(condition, dict):
            if "$contains" in condition and condition["$contains"] not in str(value):
                return False
            if "$in" in condition and value not in condition["$in"]:
                return False
        elif value != condition:
            return False
    return True


def test_chroma_query_signature_matches_local_vector_store():
    assert inspect.signature(ChromaVectorStore.query) == inspect.signature(
        LocalVectorStore.query
    )


def test_chroma_store_add_chunks_and_query_with_metadata_filters():
    store = ChromaVectorStore(
        collection=FakeCollection(),
        embedding_client=FakeEmbeddingClient(),
        relevance_threshold=2.0,
    )
    store.add_chunks(
        document_id=1,
        document_title="玩家动机手册",
        doc_type="theory",
        stages=["design", "analysis"],
        tags=["motivation"],
        scenario="onboarding",
        priority=8,
        chunks=[
            ChunkResult(
                content="玩家动机来自成长感。",
                heading_context="第一章 > 动机",
                chunk_index=0,
            )
        ],
    )
    store.add_chunks(
        document_id=2,
        document_title="定价研究",
        doc_type="research",
        stages=["report"],
        tags=["pricing"],
        scenario="pricing",
        priority=3,
        chunks=[
            ChunkResult(
                content="价格清晰度会影响转化。",
                heading_context="第二章 > 定价",
                chunk_index=0,
            )
        ],
    )

    results = store.query(
        "玩家动机",
        stages=["design"],
        doc_types=["theory"],
        scenarios=["onboarding"],
        top_k=5,
    )

    assert len(results) == 1
    assert results[0]["document_id"] == 1
    assert results[0]["document_title"] == "玩家动机手册"
    assert results[0]["content"] == "玩家动机来自成长感。"


def test_chroma_store_filters_out_results_beyond_relevance_threshold():
    store = ChromaVectorStore(
        collection=FakeCollection(),
        embedding_client=FakeEmbeddingClient(),
        relevance_threshold=0.5,
    )
    store.add_chunks(
        document_id=1,
        document_title="留存研究",
        doc_type="research",
        stages=["analysis"],
        tags=[],
        scenario=None,
        priority=0,
        chunks=[
            ChunkResult(content="留存和回流相关。", heading_context="留存", chunk_index=0),
            ChunkResult(content="价格清晰度会影响转化。", heading_context="定价", chunk_index=1),
        ],
    )

    results = store.query("留存", stages=["analysis"], top_k=5)

    assert len(results) == 1
    assert results[0]["content"] == "留存和回流相关。"


def test_chroma_store_dedupes_adjacent_chunks_from_same_document():
    store = ChromaVectorStore(
        collection=FakeCollection(),
        embedding_client=FakeEmbeddingClient(),
        relevance_threshold=2.0,
    )
    store.add_chunks(
        document_id=1,
        document_title="方法论",
        doc_type="guide",
        stages=["design"],
        tags=[],
        scenario=None,
        priority=9,
        chunks=[
            ChunkResult(content="玩家动机来自成长感。", heading_context="方法", chunk_index=0),
            ChunkResult(content="玩家动机还会受到目标感影响。", heading_context="方法", chunk_index=1),
        ],
    )
    store.add_chunks(
        document_id=2,
        document_title="领域研究",
        doc_type="research",
        stages=["design"],
        tags=[],
        scenario=None,
        priority=5,
        chunks=[
            ChunkResult(content="留存依赖长期价值。", heading_context="研究", chunk_index=0),
        ],
    )

    results = store.query("玩家动机", stages=["design"], top_k=5)

    assert [item["document_title"] for item in results] == ["方法论", "领域研究"]
