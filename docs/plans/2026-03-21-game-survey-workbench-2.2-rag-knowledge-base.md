# Game Survey Workbench 2.2 — RAG Knowledge Base

> **Type:** Architecture upgrade (storage backend replacement)
> **Status:** Draft
> **Created:** 2026-03-21
> **Predecessor:** 2.0 (complete), 2.1 UI uplift (in progress)

---

## Goal

Replace the TF-IDF + JSON file vector store with a ChromaDB-backed semantic retrieval system using OpenAI embeddings, enabling the knowledge base to handle 10+ books (tens of MB each, 20k-50k chunks total) with high-precision search.

## Scope

- Replace `LocalVectorStore` (TF-IDF, `chunks.json`) with `ChromaVectorStore` (ChromaDB embedded mode)
- Add `EmbeddingClient` for OpenAI `/v1/embeddings` API
- Upgrade chunking strategy: overlap + heading-aware splitting
- Make document ingestion async (background task with status tracking)
- Clean-slate migration: discard existing `chunks.json`, rebuild from scratch

## Non-goals

| Out of scope | Reason |
|---|---|
| Multi-collection / multi-tenant | Single-user product |
| Reranker implementation | Interface reserved, deferred to 2.3+ |
| Streaming progress (WebSocket/SSE) | Status polling is sufficient |
| Image/table multimodal embedding | Text-only books |
| Replace SQLite metadata table | ChromaDB handles vectors only; document metadata stays in SQLite |
| Frontend framework (React/Vue) | Stays on Jinja2 + Pico CSS |

---

## Design Direction: ChromaDB Embedded Mode

### Why ChromaDB

| Criteria | ChromaDB | LanceDB | sqlite-vec |
|---|---|---|---|
| Metadata filtering | Native `$and/$or`, `$contains`, `$in` | SQL-style, expressive | Basic comparisons only |
| 50k chunk scale | Comfortable (HNSW) | Comfortable | Brute-force, slow |
| Python API | Excellent, Pythonic | Good, evolving | Raw SQL |
| Persistence | Built-in `PersistentClient` | Lance columnar files | Native SQLite |
| Community | 26k stars, most FastAPI examples | 9k stars | 6.7k stars |
| Dependency weight | Heavy (~500MB with ONNX) | Medium (~150-200MB) | Very light (~few MB) |

ChromaDB wins on API quality, metadata filtering, and ecosystem maturity. ONNX bloat is mitigated by using external OpenAI embeddings (skip built-in embedding function).

Qdrant local mode rejected: 20k soft limit < our 50k requirement.
Bare FAISS rejected: no native metadata filtering or persistence.

---

## Architecture Changes

### Before

```
routes/knowledge.py
  → services/knowledge_ingest.py
    → retrieval/store.py  (LocalVectorStore: TF-IDF + chunks.json)
```

### After

```
routes/knowledge.py
  → services/knowledge_ingest.py
    → retrieval/embeddings.py  (NEW: OpenAI embedding client)
    → retrieval/store.py       (ChromaVectorStore: ChromaDB + HNSW)
```

### File Change Matrix

| File | Action | Description |
|---|---|---|
| `retrieval/store.py` | **Rewrite** | `LocalVectorStore` → `ChromaVectorStore`, same `query()` / `query_layered()` signatures |
| `retrieval/embeddings.py` | **New** | OpenAI `/v1/embeddings` client with batch support and retry |
| `retrieval/chunking.py` | **Enhance** | Overlap + heading-aware splitting, `ChunkResult.heading_context` |
| `config.py` | **Extend** | Embedding env vars |
| `services/knowledge_ingest.py` | **Adapt** | Async ingestion with background embedding + ChromaDB write |
| `models/knowledge.py` | **Extend** | `index_status`, `index_error`, `chunk_count` fields |
| `templates/knowledge/detail.html` | **Enhance** | Index status display (indexing/ready/failed) |
| `app.py` | **Minor** | Initialize ChromaDB client in lifespan |
| `pyproject.toml` | **Deps** | Add `chromadb`, `openai` |

### Unchanged

- All `routes/*.py` upper-level logic
- All other `templates/*.html`
- `services/knowledge_parser.py`, `knowledge_convert.py`
- `models/knowledge.py` existing fields

---

## Storage Layout

```
workspace/
  app.db                              # SQLite (unchanged)
  knowledge/                          # Raw markdown files (unchanged)
  artifacts/
    vector_store/
      chunks.json                     # DEPRECATED: delete on first startup
    chroma_db/                        # NEW: ChromaDB persistent directory
      chroma.sqlite3                  # ChromaDB internal index
      *.bin                           # HNSW vector files
```

## ChromaDB Collection Design

Single collection: `knowledge_chunks`

```python
{
    "id": "doc-{document_id}-chunk-{index}",
    "documents": ["[heading_context] chunk text..."],
    "embeddings": [[0.012, -0.034, ...]],
    "metadatas": [{
        "document_id": 42,
        "document_title": "游戏设计心理学",
        "doc_type": "theory",
        "stages": "design,analysis",        # Comma-separated (ChromaDB no array support)
        "tags": "心理学,用户行为",
        "scenario": "player_motivation",
        "priority": 8,
        "chunk_index": 3
    }]
}
```

## Query Mapping

| Current interface | ChromaDB implementation |
|---|---|
| `query(text, stages, doc_types, top_k)` | `collection.query(query_embeddings=[embed(text)], where={...}, n_results=top_k*3)` → threshold filter → dedupe → truncate |
| `query_layered(text, selected_titles, ...)` | Two queries: method pool (`priority >= 8`) then domain pool, merge and dedupe |
| `add_chunks(doc, chunks)` | `collection.add(ids, documents, embeddings, metadatas)` |
| `delete_document(doc_id)` | `collection.delete(where={"document_id": doc_id})` |

---

## Embedding Client

```python
# retrieval/embeddings.py

class EmbeddingClient:
    def __init__(self, api_key: str, base_url: str, model: str, dimensions: int | None = None):
        ...

    async def embed(self, text: str) -> list[float]:
        """Single text embedding."""

    async def embed_batch(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        """Batch embedding with automatic chunking to avoid token limits."""
```

### New Environment Variables

```
GAME_SURVEY_WORKBENCH_EMBEDDING_API_KEY       # OpenAI API key
GAME_SURVEY_WORKBENCH_EMBEDDING_BASE_URL      # Default: https://api.openai.com/v1
GAME_SURVEY_WORKBENCH_EMBEDDING_MODEL         # Default: text-embedding-3-small
GAME_SURVEY_WORKBENCH_EMBEDDING_DIMENSIONS    # Optional dimension reduction
GAME_SURVEY_WORKBENCH_RELEVANCE_THRESHOLD     # Default: 1.2 (L2 distance cutoff)
```

---

## Chunking Strategy Upgrade

### Current

- Fixed 800 chars, paragraph boundary alignment, no overlap

### New

```python
def split_markdown(
    content: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    respect_headers: bool = True
) -> list[ChunkResult]:
```

**Split priority:**
1. Header lines (`#`, `##`, `###`) → force break (never cross chapter boundaries)
2. Within chunk_size, prefer paragraph boundaries (blank lines)
3. Within long paragraphs, break at sentence endings (。？！.?!)
4. Tail of each chunk overlaps into next chunk prefix by `chunk_overlap` chars

### ChunkResult Enhancement

```python
@dataclass
class ChunkResult:
    content: str
    heading_context: str    # NEW: "第三章 > 3.2 玩家动机"
    chunk_index: int
```

Stored document text format: `[heading_context] content`

---

## Async Ingestion Flow

### Problem

A book with 2000-5000 chunks needs 20-50 OpenAI API calls (batch_size=100), taking 30-60 seconds. Synchronous POST → redirect will timeout.

### Solution: Background Task + Status Polling

```python
async def ingest_knowledge_file(path, session, settings) -> IngestKnowledgeResult:
    # 1. Parse frontmatter (sync, fast)
    # 2. Split into chunks (sync, fast)
    # 3. Write SQLite record with index_status="indexing" (fast)
    # 4. Launch background task: embed + write ChromaDB
    #    Success → index_status="ready", chunk_count=N
    #    Failure → index_status="index_failed", index_error="..."
    return IngestKnowledgeResult(title=..., chunk_count=..., status="indexing")
```

### Model Extension

```python
class KnowledgeDocument(SQLModel, table=True):
    # ... existing fields unchanged ...
    index_status: str = "pending"       # pending → indexing → ready → index_failed
    index_error: str | None = None
    chunk_count: int = 0
```

### UI Status Display

| index_status | Display |
|---|---|
| `indexing` | 🔄 正在建立索引... (auto-refresh) |
| `ready` | ✅ 已就绪 · 1,234 chunks |
| `index_failed` | ❌ 索引失败 · [重试] |

Documents with `indexing` status are excluded from retrieval results.

Background tasks use `asyncio.create_task()` — no external queue (Celery etc.), stays local-first.

---

## Retrieval Precision Strategy

### Layer 1: Embedding Quality

- Default: `text-embedding-3-small` (1536 dims), switchable to `text-embedding-3-large` (3072 dims)
- Chunk text prefixed with `heading_context` for chapter-aware embedding

### Layer 2: Over-fetch + Filter + Dedupe

```python
def query(self, text, stages, doc_types, top_k=5):
    # 1. Vector search: fetch top_k * 3 candidates
    raw = collection.query(
        query_embeddings=[embed(text)],
        where=build_filter(stages, doc_types),
        n_results=top_k * 3
    )
    # 2. Relevance gate: discard distance > threshold
    filtered = [r for r in raw if r.distance <= self.relevance_threshold]
    # 3. Dedupe: adjacent chunks from same document → keep best
    deduped = dedupe_adjacent_chunks(filtered)
    # 4. Return top_k
    return deduped[:top_k]
```

### Layer 3: Reranker Interface (Reserved, NOT implemented in 2.2)

```python
class ChromaVectorStore:
    def __init__(self, ..., reranker: Reranker | None = None):
        self.reranker = reranker  # Default None, future cross-encoder slot

    def query(self, text, ...):
        candidates = self._vector_search(...)
        if self.reranker:
            candidates = self.reranker.rerank(text, candidates)
        return candidates[:top_k]
```

### Relevance Threshold

- Default `1.2` (ChromaDB L2 distance; lower = more similar)
- Configurable via `GAME_SURVEY_WORKBENCH_RELEVANCE_THRESHOLD`
- Tuned based on real usage feedback

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| OpenAI embedding API unavailable/timeout | High | Retry 3x with exponential backoff; failed ingestion marked `index_failed` with retry button; failed retrieval returns empty + user message, no crash |
| ChromaDB package bloat (ONNX) | Medium | Skip built-in embedding function; if still bloated, `pip install chromadb --no-deps` + manual deps |
| Long initial ingestion for 10+ books | Medium | Batch embedding (100/batch) + status UI; ~10 min total, acceptable |
| Chunking strategy change affects retrieval quality | Medium | A/B test with 2-3 books: compare old TF-IDF vs new vector top-5 results manually |
| ChromaDB version upgrade breaks persistence | Low | Pin minor version in pyproject.toml; clean-slate policy reduces migration burden |
| heading_context prefix wastes embedding tokens | Low | Heading chain typically < 50 chars vs 1000 char chunk (< 5%), negligible |

---

## TDD Implementation Tasks

### Task 1: EmbeddingClient

- **Test:** Mock OpenAI API, verify `embed()` returns correct dimensions; `embed_batch()` splits at batch_size boundary; retry on 429/500
- **Implement:** `retrieval/embeddings.py`
- **Files:** `retrieval/embeddings.py`, `tests/test_embeddings.py`

### Task 2: Chunking Strategy Upgrade

- **Test:** Split a sample markdown with headers → verify no chunk crosses header boundary; verify overlap exists; verify `heading_context` correctness
- **Implement:** Enhance `retrieval/chunking.py`
- **Files:** `retrieval/chunking.py`, `tests/test_chunking.py`

### Task 3: ChromaVectorStore Core

- **Test:** Add chunks with metadata → query with filters → verify correct results returned; verify distance threshold filtering; verify adjacent chunk dedup
- **Implement:** `retrieval/store.py` (new `ChromaVectorStore` class)
- **Files:** `retrieval/store.py`, `tests/test_chroma_store.py`

### Task 4: ChromaVectorStore Layered Query

- **Test:** Method pool (priority >= 8) vs domain pool separation; selected_titles prioritization; cross-pool dedup
- **Implement:** `query_layered()` method
- **Files:** `retrieval/store.py`, `tests/test_chroma_store.py`

### Task 5: Async Ingestion Pipeline

- **Test:** Ingest a document → verify SQLite record created with `index_status="indexing"` → background task completes → status becomes `ready` with correct `chunk_count`; simulate embedding failure → status becomes `index_failed`
- **Implement:** Update `services/knowledge_ingest.py`
- **Files:** `services/knowledge_ingest.py`, `models/knowledge.py`, `tests/test_knowledge_ingest.py`

### Task 6: Config & App Initialization

- **Test:** Verify ChromaDB client initializes with correct path; verify env vars parsed correctly; verify old `chunks.json` not loaded
- **Implement:** Update `config.py`, `app.py`
- **Files:** `config.py`, `app.py`, `tests/test_config.py`

### Task 7: Knowledge UI Status Display

- **Test:** Render knowledge list template with documents in each status → verify correct status badges; verify "retry" button appears for failed documents
- **Implement:** Update `templates/knowledge/detail.html`
- **Files:** `templates/knowledge/detail.html`, `routes/knowledge.py`, `tests/test_knowledge_routes.py`

### Task 8: Integration Test & Cleanup

- **Test:** End-to-end: upload a markdown file → verify chunks in ChromaDB → query returns relevant results → delete document → verify chunks removed
- **Implement:** Remove `chunks.json` references, update startup to skip old vector store
- **Files:** `tests/test_integration_rag.py`

---

## Verification / Acceptance Criteria

1. `pytest tests/ -v --tb=short` — all tests pass
2. `python -m compileall src/game_survey_workbench` — no compilation errors
3. Upload a 1MB+ markdown document → ingestion completes within 120 seconds → status shows "ready"
4. Query a known topic from the uploaded document → top-3 results contain relevant chunks
5. Delete a document → its chunks no longer appear in search results
6. Simulate embedding API failure → document shows "index_failed" → retry button works
7. Application starts with empty `chroma_db/` directory → no errors
8. Application starts with existing `chroma_db/` directory → existing index is preserved
9. `chunks.json` is ignored — old TF-IDF code path is fully removed

---

## Codex Agent 执行指令

```
打开项目目录 C:\Users\69050\Documents\Playground

使用 superpowers:executing-plans 技能，逐任务执行以下计划：
docs/plans/2026-03-21-game-survey-workbench-2.2-rag-knowledge-base.md

每个 Task 严格按 Step 顺序执行：写测试 → 确认失败 → 实现 → 确认通过 → 提交。
不要跳步骤，不要合并 Task。每个 commit 对应一个 Task。

Task 1 特别注意：EmbeddingClient 需要支持 async，mock 测试时用 httpx mock 而非 requests。
Task 3 特别注意：ChromaVectorStore 的 query() 签名必须与现有 LocalVectorStore.query() 兼容。
Task 5 特别注意：后台任务用 asyncio.create_task()，测试时需要 await 任务完成后再断言状态。

最终 Task 8 必须：
1. pytest tests/ -v --tb=short 全部通过
2. python -m compileall src/game_survey_workbench 无错误
3. 上传一份 1MB+ markdown 文件验证端到端流程
```
