from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path


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
        top_method_k: int = 3,
        top_domain_k: int = 5,
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
