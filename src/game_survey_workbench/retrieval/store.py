from __future__ import annotations

import asyncio
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from game_survey_workbench.retrieval.chunking import ChunkResult

DEFAULT_PROJECT_KNOWLEDGE_TOP_K = 20


@dataclass
class StoredChunk:
    document_title: str
    content: str
    stages: list[str]
    doc_type: str
    tags: list[str]
    scenario: str | None = None
    priority: int = 0


class LocalVectorStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "chunks.json"

    def save_chunks(self, chunks: list[StoredChunk]) -> None:
        existing = self.load_chunks()
        existing.extend(asdict(chunk) for chunk in chunks)
        self.index_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_chunks(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _tokenize(self, text: str) -> list[str]:
        lowered = text.lower()
        latin_tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", lowered)
        cjk_tokens = re.findall(r"[\u4e00-\u9fff]", text)
        return latin_tokens + cjk_tokens

    def _compute_idf(self, term: str, chunks: list[dict]) -> float:
        document_frequency = sum(
            1
            for chunk in chunks
            if term in self._tokenize(
                f"{chunk.get('document_title', '')} {chunk.get('content', '')}"
            )
        )
        return math.log((1 + len(chunks)) / (1 + document_frequency)) + 1.0

    def _tfidf_score(self, query_terms: list[str], chunk: dict, all_chunks: list[dict]) -> float:
        tokens = self._tokenize(
            f"{chunk.get('document_title', '')} {chunk.get('content', '')}"
        )
        total_terms = max(len(tokens), 1)
        score = 0.0
        for term in query_terms:
            term_frequency = tokens.count(term) / total_terms
            if term_frequency == 0:
                continue
            score += term_frequency * self._compute_idf(term, all_chunks)
        return score

    def query(
        self,
        query: str,
        *,
        stages: list[str] | None = None,
        doc_types: list[str] | None = None,
        scenarios: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[dict]:
        terms = self._tokenize(query)
        filtered_chunks: list[dict] = []

        for item in self.load_chunks():
            if stages and not set(stages).intersection(item.get("stages", [])):
                continue
            if doc_types and item.get("doc_type") not in doc_types:
                continue
            if scenarios and item.get("scenario") not in scenarios:
                continue
            filtered_chunks.append(item)

        matches: list[tuple[tuple[float, int], dict]] = []
        for item in filtered_chunks:
            score = self._tfidf_score(terms, item, filtered_chunks) if terms else 0.0
            if score > 0 or not terms:
                priority = int(item.get("priority", 0))
                matches.append(((score, priority), item))

        matches.sort(key=lambda pair: pair[0], reverse=True)
        if top_k is not None:
            matches = matches[:top_k]
        return [item for _, item in matches]

    def query_layered(
        self,
        query: str,
        *,
        selected_document_titles: list[str],
        task_stages: list[str],
        top_method_k: int = DEFAULT_PROJECT_KNOWLEDGE_TOP_K,
        top_domain_k: int = DEFAULT_PROJECT_KNOWLEDGE_TOP_K,
    ) -> list[dict]:
        selected_titles = set(selected_document_titles)
        if not selected_titles:
            return []

        all_selected = [
            item
            for item in self.load_chunks()
            if item.get("document_title") in selected_titles
        ]
        if not all_selected:
            return []

        method_doc_types = {"guide", "theory", "method", "playbook"}
        domain_doc_types = {"experience", "research", "benchmark"}

        method_candidates = [
            item for item in all_selected
            if (
                set(task_stages).intersection(item.get("stages", []))
                and item.get("doc_type") in method_doc_types
            )
            or int(item.get("priority", 0)) >= 8
        ]
        method_candidates.sort(
            key=lambda item: (
                int(item.get("priority", 0)),
                item.get("document_title", ""),
                item.get("content", ""),
            ),
            reverse=True,
        )
        method_results = [
            {**item, "retrieval_pool": "method"}
            for item in method_candidates[:top_method_k]
        ]

        domain_candidates = [
            item for item in all_selected
            if item.get("doc_type") in domain_doc_types
        ]
        domain_results = [
            {**item, "retrieval_pool": "domain"}
            for item in self.query(
                query,
                stages=task_stages,
                doc_types=sorted(domain_doc_types),
                top_k=top_domain_k,
            )
            if item.get("document_title") in selected_titles
        ]

        combined: list[dict] = []
        seen_keys: set[tuple[str, str]] = set()
        for item in method_results + domain_results:
            key = (item.get("document_title", ""), item.get("content", ""))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            combined.append(item)
        return combined


class ChromaVectorStore:
    def __init__(
        self,
        *,
        collection: Any,
        embedding_client: Any,
        relevance_threshold: float = 1.2,
        reranker: Any | None = None,
    ) -> None:
        self.collection = collection
        self.embedding_client = embedding_client
        self.relevance_threshold = relevance_threshold
        self.reranker = reranker

    def add_chunks(
        self,
        *,
        document_id: int,
        document_title: str,
        doc_type: str,
        stages: list[str],
        tags: list[str],
        chunks: list[ChunkResult],
        scenario: str | None = None,
        priority: int = 0,
    ) -> None:
        self._run_async(
            self.aadd_chunks(
                document_id=document_id,
                document_title=document_title,
                doc_type=doc_type,
                stages=stages,
                tags=tags,
                chunks=chunks,
                scenario=scenario,
                priority=priority,
            )
        )

    async def aadd_chunks(
        self,
        *,
        document_id: int,
        document_title: str,
        doc_type: str,
        stages: list[str],
        tags: list[str],
        chunks: list[ChunkResult],
        scenario: str | None = None,
        priority: int = 0,
    ) -> None:
        documents = [_format_chunk_document(chunk) for chunk in chunks]
        embeddings = await self.embedding_client.embed_batch(documents)
        self.collection.add(
            ids=[
                f"doc-{document_id}-chunk-{chunk.chunk_index}"
                for chunk in chunks
            ],
            documents=documents,
            embeddings=embeddings,
            metadatas=[
                _sanitize_metadata(
                    {
                        "document_id": document_id,
                        "document_title": document_title,
                        "doc_type": doc_type,
                        "stages": ",".join(stages),
                        **{f"stage_{stage}": True for stage in stages},
                        "tags": ",".join(tags),
                        "scenario": scenario,
                        "priority": priority,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "heading_context": chunk.heading_context,
                    }
                )
                for chunk in chunks
            ],
        )

    def delete_document(self, document_id: int) -> None:
        self.collection.delete(where={"document_id": document_id})

    def query(
        self,
        query: str,
        *,
        stages: list[str] | None = None,
        doc_types: list[str] | None = None,
        scenarios: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[dict]:
        deduped = self._search_candidates(
            query,
            stages=stages,
            doc_types=doc_types,
            scenarios=scenarios,
            top_k=top_k,
        )
        if self.reranker is not None:
            deduped = self.reranker.rerank(query, deduped)
        return deduped[:top_k] if top_k is not None else deduped

    def query_layered(
        self,
        query: str,
        *,
        selected_document_titles: list[str],
        task_stages: list[str],
        top_method_k: int = DEFAULT_PROJECT_KNOWLEDGE_TOP_K,
        top_domain_k: int = DEFAULT_PROJECT_KNOWLEDGE_TOP_K,
    ) -> list[dict]:
        if not selected_document_titles:
            return []

        method_doc_types = {"guide", "theory", "method", "playbook"}
        domain_doc_types = {"experience", "research", "benchmark"}

        method_candidates = self._search_candidates(
            query,
            stages=task_stages,
            selected_document_titles=selected_document_titles,
            top_k=max(top_method_k * 3, top_method_k),
        )
        method_candidates = [
            {
                **item,
                "retrieval_pool": "method",
            }
            for item in method_candidates
            if item["priority"] >= 8
            or (
                item["doc_type"] in method_doc_types
                and set(task_stages).intersection(item["stages"])
            )
        ]
        method_candidates.sort(
            key=lambda item: (
                -int(item.get("priority", 0)),
                float(item.get("distance", 0.0)),
                item.get("document_title", ""),
                int(item.get("chunk_index", 0)),
            )
        )

        domain_candidates = self._search_candidates(
            query,
            stages=task_stages,
            doc_types=sorted(domain_doc_types),
            selected_document_titles=selected_document_titles,
            top_k=max(top_domain_k * 3, top_domain_k),
        )
        domain_candidates = [
            {
                **item,
                "retrieval_pool": "domain",
            }
            for item in domain_candidates
        ]

        combined = _dedupe_by_record_key(
            method_candidates[:top_method_k] + domain_candidates[:top_domain_k]
        )
        return combined

    def _run_async(self, coroutine: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)
        raise RuntimeError("ChromaVectorStore sync methods cannot run inside an active event loop.")

    def _search_candidates(
        self,
        query: str,
        *,
        stages: list[str] | None = None,
        doc_types: list[str] | None = None,
        scenarios: list[str] | None = None,
        selected_document_titles: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[dict]:
        embedding = self._run_async(self.embedding_client.embed(query))
        requested = top_k or 5
        raw_results = self.collection.query(
            query_embeddings=[embedding],
            where=_build_chroma_where(
                stages=stages,
                doc_types=doc_types,
                scenarios=scenarios,
                document_titles=selected_document_titles,
            ),
            n_results=max(requested * 3, requested),
        )
        candidates = _normalize_chroma_results(raw_results)
        filtered = [
            item
            for item in candidates
            if item["distance"] <= self.relevance_threshold
        ]
        deduped = _dedupe_adjacent_chunks(filtered)
        return deduped


def _format_chunk_document(chunk: ChunkResult) -> str:
    if chunk.heading_context:
        return f"[{chunk.heading_context}] {chunk.content}"
    return chunk.content


def _build_chroma_where(
    *,
    stages: list[str] | None,
    doc_types: list[str] | None,
    scenarios: list[str] | None,
    document_titles: list[str] | None = None,
) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []
    if stages:
        stage_clauses = [{f"stage_{stage}": True} for stage in stages]
        clauses.append(
            stage_clauses[0]
            if len(stage_clauses) == 1
            else {"$or": stage_clauses}
        )
    if doc_types:
        clauses.append({"doc_type": {"$in": doc_types}})
    if scenarios:
        clauses.append({"scenario": {"$in": scenarios}})
    if document_titles:
        clauses.append({"document_title": {"$in": document_titles}})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _normalize_chroma_results(raw_results: dict[str, list[list[Any]]]) -> list[dict]:
    ids = raw_results.get("ids", [[]])[0]
    documents = raw_results.get("documents", [[]])[0]
    metadatas = raw_results.get("metadatas", [[]])[0]
    distances = raw_results.get("distances", [[]])[0]
    normalized: list[dict] = []

    for record_id, document, metadata, distance in zip(
        ids, documents, metadatas, distances, strict=False
    ):
        normalized.append(
            {
                "id": record_id,
                "document_id": metadata.get("document_id"),
                "document_title": metadata.get("document_title"),
                "content": metadata.get("content") or document,
                "doc_type": metadata.get("doc_type"),
                "stages": _split_csv(metadata.get("stages")),
                "tags": _split_csv(metadata.get("tags")),
                "scenario": metadata.get("scenario"),
                "priority": int(metadata.get("priority", 0)),
                "chunk_index": int(metadata.get("chunk_index", 0)),
                "heading_context": metadata.get("heading_context", ""),
                "distance": float(distance),
            }
        )
    return normalized


def _dedupe_adjacent_chunks(items: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    for item in items:
        if any(
            item["document_id"] == existing["document_id"]
            and abs(item["chunk_index"] - existing["chunk_index"]) <= 1
            for existing in deduped
        ):
            continue
        deduped.append(item)
    return deduped


def _dedupe_by_record_key(items: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[tuple[Any, Any]] = set()
    for item in items:
        key = (item.get("document_id"), item.get("chunk_index"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item for item in value.split(",") if item]


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in metadata.items()
        if value is not None
    }
