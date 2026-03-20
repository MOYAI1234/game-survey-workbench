# Game Survey Workbench Stage 2A/2B Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Strengthen knowledge retrieval and add a real, configurable LLM runtime layer so the workbench can begin producing knowledge-grounded questionnaire and insight contexts.

**Architecture:** Keep the existing Python monolith, but upgrade the knowledge path from “parse and dump chunks” to “metadata-aware retrieval for project tasks.” In parallel, evolve the current fake-only LLM layer into a provider-agnostic runtime with explicit settings, a default OpenAI-compatible HTTP adapter, and safe failure behavior when runtime configuration is missing.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, pandas, pytest, httpx, uv.

---

## Assumptions

- The product direction is defined by `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`.
- This plan only covers Stage 2A and Stage 2B foundations.
- A concrete LLM provider has not been locked yet, so this plan uses:
  - a provider-agnostic client interface
  - an OpenAI-compatible HTTP adapter as the first real runtime
- Questionnaire grounding and insight-generation integration will be handled in the next execution plan after these foundations exist.

### Task 1: Enrich knowledge parsing metadata

**Files:**
- Modify: `src/game_survey_workbench/services/knowledge_parser.py`
- Modify: `src/game_survey_workbench/models/knowledge.py`
- Modify: `tests/test_knowledge_parser.py`

**Step 1: Write the failing test**

```python
from game_survey_workbench.services.knowledge_parser import parse_markdown_document


def test_parse_markdown_document_extracts_metadata_for_retrieval():
    raw = """---
title: Retention Framework
doc_type: theory
stage:
  - analysis
tags:
  - retention
scenario: onboarding
priority: 3
---
Body text here.
"""

    document = parse_markdown_document(raw)

    assert document.title == "Retention Framework"
    assert document.doc_type == "theory"
    assert document.stages == ["analysis"]
    assert document.tags == ["retention"]
    assert document.scenario == "onboarding"
    assert document.priority == 3
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_knowledge_parser.py -v`
Expected: FAIL because the parser does not currently expose full retrieval metadata.

**Step 3: Write minimal implementation**

Extend the parsed document shape so it includes all retrieval-relevant metadata:

```python
@dataclass
class ParsedKnowledgeDocument:
    title: str
    doc_type: str
    stages: list[str]
    tags: list[str]
    scenario: str | None
    priority: int
    body: str
```

Update parsing rules so:

- `stage` is normalized to a list
- `tags` defaults to an empty list
- `scenario` is optional
- `priority` defaults to `0`

Also ensure `KnowledgeDocument` persistence stays aligned with the parser output.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_knowledge_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/knowledge_parser.py src/game_survey_workbench/models/knowledge.py tests/test_knowledge_parser.py
git commit -m "feat: enrich knowledge metadata for retrieval"
```

### Task 2: Persist chunk metadata and add deterministic filtered retrieval

**Files:**
- Modify: `src/game_survey_workbench/services/knowledge_ingest.py`
- Modify: `src/game_survey_workbench/retrieval/store.py`
- Modify: `tests/test_knowledge_ingest.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file, retrieve_knowledge


def test_ingest_knowledge_file_persists_scenario_and_tags(tmp_path: Path):
    source = tmp_path / "doc.md"
    source.write_text(
        "---\n"
        "title: Retention Framework\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - analysis\n"
        "tags:\n"
        "  - retention\n"
        "scenario: onboarding\n"
        "---\n"
        "Players need clear goals.\n",
        encoding="utf-8",
    )

    ingest_knowledge_file(source, project_root=tmp_path)
    results = retrieve_knowledge(
        tmp_path,
        query="clear goals",
        stages=["analysis"],
        doc_types=["theory"],
        scenarios=["onboarding"],
    )

    assert results[0]["scenario"] == "onboarding"
    assert results[0]["tags"] == ["retention"]


def test_retrieve_knowledge_filters_out_non_matching_scenarios(tmp_path: Path):
    source = tmp_path / "doc.md"
    source.write_text(
        "---\n"
        "title: Event Framework\n"
        "doc_type: industry\n"
        "stage:\n"
        "  - design\n"
        "scenario: event\n"
        "---\n"
        "Reward expectations differ by event cadence.\n",
        encoding="utf-8",
    )

    ingest_knowledge_file(source, project_root=tmp_path)
    results = retrieve_knowledge(
        tmp_path,
        query="reward expectations",
        scenarios=["onboarding"],
    )

    assert results == []
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_knowledge_ingest.py -v`
Expected: FAIL because chunk storage and retrieval do not yet preserve or filter enough metadata.

**Step 3: Write minimal implementation**

Extend `StoredChunk` and persistence so chunk records include:

- `tags`
- `scenario`
- `priority`

Update ingestion so every saved chunk inherits document metadata.

Update `LocalVectorStore.query()` so it:

- filters by `stages`, `doc_types`, and `scenarios`
- returns deterministic top matches
- sorts by simple lexical score first and then `priority` as a tie-breaker

Suggested scoring shape:

```python
score = sum(term in haystack for term in terms)
priority = int(item.get("priority", 0))
matches.append(((score, priority), item))
matches.sort(key=lambda pair: pair[0], reverse=True)
```

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_knowledge_ingest.py tests/test_knowledge_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/knowledge_ingest.py src/game_survey_workbench/retrieval/store.py tests/test_knowledge_ingest.py
git commit -m "feat: add metadata-aware retrieval filtering"
```

### Task 3: Add project-aware retrieval helper for downstream workflows

**Files:**
- Modify: `src/game_survey_workbench/services/knowledge_ingest.py`
- Modify: `src/game_survey_workbench/services/projects.py`
- Create: `tests/test_retrieval_service.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file, retrieve_project_knowledge
from game_survey_workbench.services.projects import create_project


def test_retrieve_project_knowledge_uses_project_knowledge_pack_filters(tmp_path: Path):
    source = tmp_path / "doc.md"
    source.write_text(
        "---\n"
        "title: Retention Framework\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - design\n"
        "scenario: onboarding\n"
        "---\n"
        "Use behavior and attitude questions together.\n",
        encoding="utf-8",
    )

    ingest_knowledge_file(source, project_root=tmp_path)
    create_project(
        workspace_root=tmp_path,
        slug="demo",
        name="Demo",
        knowledge_pack={"doc_types": ["theory"], "scenarios": ["onboarding"]},
    )

    results = retrieve_project_knowledge(
        workspace_root=tmp_path,
        project_slug="demo",
        query="behavior attitude questions",
        stages=["design"],
    )

    assert len(results) == 1
    assert results[0]["document_title"] == "Retention Framework"
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_retrieval_service.py -v`
Expected: FAIL because no helper currently combines project filters with retrieval.

**Step 3: Write minimal implementation**

Add a helper that:

- loads the project
- reads its `knowledge_pack`
- passes `doc_types` and `scenarios` into `retrieve_knowledge`
- accepts `stages` and `query` from the caller

Keep the helper simple and deterministic:

```python
def retrieve_project_knowledge(...):
    project = get_project(...)
    return retrieve_knowledge(
        workspace_root,
        query=query,
        stages=stages,
        doc_types=project.knowledge_pack.get("doc_types", []),
        scenarios=project.knowledge_pack.get("scenarios", []),
    )
```

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_retrieval_service.py tests/test_projects.py tests/test_knowledge_ingest.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/knowledge_ingest.py src/game_survey_workbench/services/projects.py tests/test_retrieval_service.py
git commit -m "feat: add project-aware retrieval helper"
```

### Task 4: Expand application settings for real LLM runtime configuration

**Files:**
- Modify: `src/game_survey_workbench/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
from game_survey_workbench.config import get_settings


def test_get_settings_reads_llm_runtime_configuration(monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")

    settings = get_settings()

    assert settings.llm_provider == "openai_compatible"
    assert settings.llm_model == "gpt-4.1-mini"
    assert settings.llm_api_key == "test-key"
    assert str(settings.llm_base_url) == "https://example.com/v1"
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_config.py -v`
Expected: FAIL because settings only expose `workspace_root`.

**Step 3: Write minimal implementation**

Extend `Settings` with:

- `llm_provider: str | None`
- `llm_model: str | None`
- `llm_api_key: str | None`
- `llm_base_url: str | None`

Read from environment:

- `GAME_SURVEY_WORKBENCH_LLM_PROVIDER`
- `GAME_SURVEY_WORKBENCH_LLM_MODEL`
- `GAME_SURVEY_WORKBENCH_LLM_API_KEY`
- `GAME_SURVEY_WORKBENCH_LLM_BASE_URL`

Do not add validation logic yet beyond storing values.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/config.py tests/test_config.py
git commit -m "feat: add llm runtime settings"
```

### Task 5: Add provider-agnostic runtime client selection and missing-config failure

**Files:**
- Modify: `src/game_survey_workbench/llm/client.py`
- Modify: `tests/test_insights_service.py`
- Create: `tests/test_llm_client.py`

**Step 1: Write the failing tests**

```python
import pytest

from game_survey_workbench.config import Settings
from game_survey_workbench.llm.client import build_llm_client, MissingLLMConfigurationError


def test_build_llm_client_rejects_missing_runtime_configuration():
    settings = Settings(
        workspace_root="workspace",
        llm_provider=None,
        llm_model=None,
        llm_api_key=None,
        llm_base_url=None,
    )

    with pytest.raises(MissingLLMConfigurationError):
        build_llm_client(settings)


def test_build_llm_client_returns_openai_compatible_client():
    settings = Settings(
        workspace_root="workspace",
        llm_provider="openai_compatible",
        llm_model="demo-model",
        llm_api_key="test-key",
        llm_base_url="https://example.com/v1",
    )

    client = build_llm_client(settings)

    assert client.__class__.__name__ == "OpenAICompatibleLLMClient"
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_llm_client.py -v`
Expected: FAIL because only `FakeLLMClient` exists.

**Step 3: Write minimal implementation**

Add:

- `MissingLLMConfigurationError`
- `OpenAICompatibleLLMClient`
- `build_llm_client(settings)`

Suggested structure:

```python
class MissingLLMConfigurationError(RuntimeError):
    pass


@dataclass
class OpenAICompatibleLLMClient:
    model: str
    api_key: str
    base_url: str

    def generate(self, prompt: str) -> str:
        raise NotImplementedError


def build_llm_client(settings: Settings) -> LLMClient:
    if not settings.llm_provider or not settings.llm_model or not settings.llm_api_key or not settings.llm_base_url:
        raise MissingLLMConfigurationError("LLM runtime is not configured.")
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleLLMClient(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
    raise MissingLLMConfigurationError(f"Unsupported LLM provider: {settings.llm_provider}")
```

Do not implement HTTP request execution yet in this task; only runtime selection and failure behavior.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_llm_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/llm/client.py tests/test_llm_client.py
git commit -m "feat: add llm client selection and config errors"
```

### Task 6: Implement OpenAI-compatible HTTP prompt execution with test doubles

**Files:**
- Modify: `src/game_survey_workbench/llm/client.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_llm_client.py`

**Step 1: Write the failing test**

```python
import httpx

from game_survey_workbench.llm.client import OpenAICompatibleLLMClient


def test_openai_compatible_client_posts_prompt_and_returns_text(monkeypatch):
    captured = {}

    def fake_post(self, url, *, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "Generated answer"}
                        ]
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = OpenAICompatibleLLMClient(
        model="demo-model",
        api_key="test-key",
        base_url="https://example.com/v1",
    )

    result = client.generate("Hello")

    assert result == "Generated answer"
    assert captured["url"] == "https://example.com/v1/responses"
    assert captured["json"]["model"] == "demo-model"
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_llm_client.py -v`
Expected: FAIL because the real client does not yet perform HTTP requests.

**Step 3: Write minimal implementation**

Move `httpx` into runtime dependencies and implement `OpenAICompatibleLLMClient.generate()` with:

- `POST {base_url}/responses`
- bearer auth header
- payload:

```python
{
    "model": self.model,
    "input": prompt,
}
```

Parse the first available output text block and return it.

If response parsing fails, raise a clear `RuntimeError`.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_llm_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml src/game_survey_workbench/llm/client.py tests/test_llm_client.py
git commit -m "feat: add openai-compatible llm runtime adapter"
```

## Verification Checklist Before Any Implementation Claim

- Run: `python -m uv run pytest tests/test_knowledge_parser.py tests/test_knowledge_ingest.py tests/test_retrieval_service.py tests/test_config.py tests/test_llm_client.py tests/test_projects.py tests/test_questionnaire_service.py tests/test_insights_service.py -v`
- Run: `python -m uv run pytest -v`
- Run: `python -m uv run python -m compileall src`
- Manually confirm:
  - knowledge ingestion persists scenario, tags, and priority into chunk storage
  - retrieval respects project knowledge-pack filters
  - missing LLM runtime config fails clearly
  - configured runtime can make a testable HTTP call through the provider adapter

## Risks and Notes

- Do not let provider-specific details leak into questionnaire or insight services; keep them behind `build_llm_client()`.
- Keep retrieval deterministic for tests even if later embedding-based ranking is added.
- Do not skip the missing-config path; local-first tools need clear setup failure behavior.
- This plan intentionally stops short of wiring questionnaire generation and insight synthesis to the real runtime. That belongs in the next Stage 2 implementation plan.
