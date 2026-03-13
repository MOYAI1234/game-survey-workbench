from __future__ import annotations

import json
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

    def query(
        self,
        query: str,
        *,
        stages: list[str] | None = None,
        doc_types: list[str] | None = None,
        scenarios: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[dict]:
        terms = [item.lower() for item in query.split() if item.strip()]
        matches: list[tuple[tuple[int, int], dict]] = []

        for item in self.load_chunks():
            if stages and not set(stages).intersection(item.get("stages", [])):
                continue
            if doc_types and item.get("doc_type") not in doc_types:
                continue
            if scenarios and item.get("scenario") not in scenarios:
                continue

            haystack = f"{item.get('document_title', '')} {item.get('content', '')}".lower()
            score = sum(term in haystack for term in terms)
            if score or not terms:
                priority = int(item.get("priority", 0))
                matches.append(((score, priority), item))

        matches.sort(key=lambda pair: pair[0], reverse=True)
        if top_k is not None:
            matches = matches[:top_k]
        return [item for _, item in matches]
