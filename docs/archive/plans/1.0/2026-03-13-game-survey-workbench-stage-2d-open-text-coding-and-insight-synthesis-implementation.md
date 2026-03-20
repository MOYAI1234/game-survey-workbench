# Game Survey Workbench Stage 2D: Open-Text Coding and Insight Synthesis Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the analysis side of the workbench knowledge-guided by routing open-text responses through LLM-supported coding, combining deterministic findings with retrieved knowledge into grounded insight narratives, and preserving structured evidence for downstream reporting.

**Architecture:** Extend the existing Python monolith. Reuse Stage 2A/2B retrieval and LLM infrastructure. Reuse Stage 2C patterns for context assembly, citation persistence, and prompt loading. Keep deterministic analysis and LLM interpretation clearly separated.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, pytest, pandas

---

## Assumptions

- Product direction remains defined by `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`
- Stage scope remains defined by `docs/plans/2026-03-13-game-survey-workbench-stage-2-llm-knowledge-plan.md`
- Stage 2A, 2B, and 2C foundations are complete on `master` (44 tests passing)
- Stage 2D should not introduce embedding retrieval changes or Stage 3 context-layer work
- Stage 2D should not change the questionnaire grounding flow from Stage 2C
- The existing `services/insights.py` skeleton and prompt placeholders are the starting point

## What Already Exists

| Component | State | Location |
|-----------|-------|----------|
| `free_text` column detection | Working | `services/dataset_import.py` |
| `other_text_column` linking | Working | `services/dataset_import.py:96-108` |
| Scale/choice/multi-select analytics | Working | `services/analytics.py` |
| `AnalysisRunRecord` persistence | Working | `models/analysis_run.py` |
| `insights.py` skeleton | Scaffold only | `services/insights.py` |
| `open_text_coding.md` prompt | 1-line placeholder | `llm/prompts/open_text_coding.md` |
| `insight_synthesis.md` prompt | 2-line placeholder | `llm/prompts/insight_synthesis.md` |
| Retrieval + project filtering | Working | `services/knowledge_ingest.py` |
| LLM client + FakeLLMClient | Working | `llm/client.py` |
| Report Markdown rendering | Working | `services/reporting.py` |

## Architecture Direction

Stage 2D introduces two new service-layer workflows that sit between dataset import and report generation:

```
Dataset Import (deterministic)
    |
    v
Open-Text Coding (LLM-assisted, per question)
    |
    v
Deterministic Analytics (unchanged)
    |
    v
Insight Synthesis (LLM-assisted, per analysis run)
    |
    v
Report Generation (consumes saved outputs)
```

### New Service Boundaries

- `services/text_coding.py` — open-text coding service
  - accepts a question column's free-text responses + project knowledge
  - calls LLM to cluster responses into coded themes
  - returns structured `CodingResult` with themes, counts, and evidence snippets
  - persists results per analysis run

- `services/insights.py` — upgrade from scaffold to full service
  - accepts deterministic findings + coded themes + project knowledge
  - calls LLM to produce grounded narrative insights
  - returns `InsightSynthesisResult` with narrative, structured citations, and evidence
  - persists results per analysis run

### Data Flow Contracts

**Open-Text Coding Input:**
- `analysis_run_id` — ties to existing run
- `question_column` — the column name being coded
- `responses` — list of raw text responses (from CSV)
- `knowledge_snippets` — retrieved from project knowledge (stage: `analysis`)

**Open-Text Coding Output (persisted):**
- `themes` — list of `{theme_name, count, example_responses, evidence_snippet}`
- `uncoded_count` — responses that did not match any theme
- `citations` — knowledge documents that influenced the coding

**Insight Synthesis Input:**
- `analysis_run_id`
- `research_goal` — from project or questionnaire context
- `statistical_findings` — deterministic outputs from analytics
- `coded_themes` — from text coding results
- `knowledge_snippets` — retrieved from project knowledge (stage: `analysis`)

**Insight Synthesis Output (persisted):**
- `narrative` — Markdown text with inline citations
- `evidence_section` — structured `## Evidence Basis` section (parallel to 2C's `## Knowledge Basis`)
- `citations` — structured list of referenced knowledge + theme sources

---

## Tasks

### Task 1: Add `CodingResult` persistence model

**Files:**
- Create: `src/game_survey_workbench/models/text_coding.py`
- Modify: `tests/test_text_coding_service.py` (new file)

**Step 1: Write the failing test**

```python
from game_survey_workbench.models.text_coding import CodingResult


def test_coding_result_stores_themes_and_citations():
    result = CodingResult(
        analysis_run_id="run-1",
        question_column="Why did you leave?",
        themes=[
            {"theme_name": "Boredom", "count": 12, "example_responses": ["got bored"]},
        ],
        uncoded_count=3,
        citations=[{"document_title": "Churn Framework", "content": "Boredom is top driver."}],
    )

    assert result.themes[0]["theme_name"] == "Boredom"
    assert result.uncoded_count == 3
    assert result.citations[0]["document_title"] == "Churn Framework"
```

**Step 2:** Run test to verify failure.

**Step 3: Implement**

```python
# models/text_coding.py
class CodingResult(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    analysis_run_id: str = Field(index=True)
    question_column: str
    themes: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    uncoded_count: int = 0
    citations: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

Register the new table in `db.py` imports so `create_db_and_tables` picks it up.

**Step 4:** Run test to verify pass.

**Step 5:** Commit: `feat: add CodingResult persistence model`

---

### Task 2: Add `top_k` parameter to retrieval and retrieval stage filter for analysis

**Files:**
- Modify: `src/game_survey_workbench/retrieval/store.py`
- Modify: `tests/test_retrieval_service.py`

**Step 1: Write the failing test**

```python
def test_query_respects_top_k_limit(tmp_path):
    store = LocalVectorStore(tmp_path)
    store.save_chunks([
        StoredChunk(document_title=f"Doc {i}", content=f"content {i}", stages=["analysis"], doc_type="theory", tags=[]),
        for i in range(20)
    ])

    results = store.query("content", top_k=5)
    assert len(results) == 5
```

**Step 2:** Run test to verify failure.

**Step 3: Implement**

Add `top_k: int | None = None` parameter to `LocalVectorStore.query()`. If set, slice results after sorting: `matches = matches[:top_k]`.

Propagate `top_k` through `retrieve_knowledge()` and `retrieve_project_knowledge()` as an optional parameter.

**Step 4:** Run test to verify pass. Run full suite to verify no regressions.

**Step 5:** Commit: `feat: add top_k limit to retrieval queries`

---

### Task 3: Build open-text coding prompt and context assembly

**Files:**
- Modify: `src/game_survey_workbench/llm/prompts/open_text_coding.md`
- Create: `src/game_survey_workbench/services/text_coding.py`
- Modify: `tests/test_text_coding_service.py`

**Step 1: Write the failing tests**

```python
from game_survey_workbench.services.text_coding import (
    build_coding_context,
    load_coding_prompt,
    parse_coding_response,
)


def test_build_coding_context_includes_responses_and_knowledge():
    context = build_coding_context(
        question="Why did you stop playing?",
        responses=["got bored", "too hard", "no time", "got bored of rewards"],
        knowledge_snippets=[
            {"document_title": "Churn Study", "content": "Boredom and difficulty are top churn drivers."}
        ],
    )

    assert "Why did you stop playing?" in context
    assert "got bored" in context
    assert "Churn Study" in context


def test_load_coding_prompt_contains_theme_instruction():
    prompt = load_coding_prompt()
    assert "theme" in prompt.lower()


def test_parse_coding_response_extracts_themes():
    raw = (
        '{"themes": [{"theme_name": "Boredom", "count": 2, '
        '"example_responses": ["got bored", "got bored of rewards"]}], '
        '"uncoded_count": 0}'
    )
    result = parse_coding_response(raw)
    assert result["themes"][0]["theme_name"] == "Boredom"
    assert result["uncoded_count"] == 0
```

**Step 2:** Run test to verify failure.

**Step 3: Implement**

- Expand `llm/prompts/open_text_coding.md` with a structured contract:
  - Input: question text, list of responses, knowledge context
  - Output: JSON with `themes` array and `uncoded_count`
  - Each theme: `theme_name`, `count`, `example_responses` (up to 3)
  - Grounding constraint: use knowledge to inform theme naming, do not fabricate

- `build_coding_context()`: format question + sampled responses + knowledge items
- `load_coding_prompt()`: read from prompt file
- `parse_coding_response()`: parse JSON from LLM output, with fallback for malformed responses

**Step 4:** Run test to verify pass.

**Step 5:** Commit: `feat: add open-text coding prompt and context assembly`

---

### Task 4: Build open-text coding orchestration with retrieval and persistence

**Files:**
- Modify: `src/game_survey_workbench/services/text_coding.py`
- Modify: `tests/test_text_coding_service.py`

**Step 1: Write the failing test**

```python
from game_survey_workbench.llm.client import FakeLLMClient
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.text_coding import code_open_text_column


def test_code_open_text_column_retrieves_knowledge_and_persists_result(tmp_path):
    # Set up knowledge
    source = tmp_path / "churn.md"
    source.write_text(
        "---\n"
        "title: Churn Framework\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - analysis\n"
        "scenario: churn\n"
        "---\n"
        "Boredom and difficulty are the top churn drivers.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)
    create_project(
        ProjectCreate(
            slug="churn-study",
            name="Churn Study",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["churn"]},
        ),
        workspace_root=tmp_path,
    )

    fake_response = (
        '{"themes": [{"theme_name": "Boredom", "count": 2, '
        '"example_responses": ["got bored", "nothing to do"]}], "uncoded_count": 1}'
    )

    result = code_open_text_column(
        project_slug="churn-study",
        analysis_run_id="run-1",
        question_column="Why did you leave?",
        responses=["got bored", "nothing to do", "idk"],
        workspace_root=tmp_path,
        client=FakeLLMClient(fake_response),
    )

    assert result.themes[0]["theme_name"] == "Boredom"
    assert result.citations[0]["document_title"] == "Churn Framework"
```

**Step 2:** Run test to verify failure.

**Step 3: Implement**

```python
def code_open_text_column(
    *,
    project_slug: str,
    analysis_run_id: str,
    question_column: str,
    responses: list[str],
    workspace_root: Path,
    client: LLMClient,
    top_k: int = 10,
) -> CodingResult:
    snippets = retrieve_project_knowledge(
        workspace_root=workspace_root,
        project_slug=project_slug,
        query=question_column,
        stages=["analysis"],
        top_k=top_k,
    )
    context = build_coding_context(
        question=question_column,
        responses=responses,
        knowledge_snippets=snippets,
    )
    prompt = load_coding_prompt()
    raw_output = client.generate(f"{prompt}\n\n{context}")
    parsed = parse_coding_response(raw_output)

    result = CodingResult(
        analysis_run_id=analysis_run_id,
        question_column=question_column,
        themes=parsed["themes"],
        uncoded_count=parsed.get("uncoded_count", 0),
        citations=snippets,
    )
    # Persist to database
    ...
    return result
```

**Step 4:** Run test to verify pass.

**Step 5:** Commit: `feat: orchestrate open-text coding with retrieval and persistence`

---

### Task 5: Upgrade insight synthesis service with structured evidence

**Files:**
- Modify: `src/game_survey_workbench/services/insights.py`
- Modify: `src/game_survey_workbench/llm/prompts/insight_synthesis.md`
- Create: `src/game_survey_workbench/models/insight.py`
- Modify: `tests/test_insights_service.py`

**Step 1: Write the failing tests**

```python
from game_survey_workbench.models.insight import InsightRecord
from game_survey_workbench.services.insights import (
    build_insight_context,
    build_insight_markdown,
    load_insight_prompt,
)


def test_insight_record_stores_narrative_and_structured_citations():
    record = InsightRecord(
        analysis_run_id="run-1",
        narrative="Boredom is the primary churn driver...",
        evidence_section="## Evidence Basis\n- Churn Framework: ...",
        citations=[{"document_title": "Churn Framework", "content": "..."}],
    )
    assert record.citations[0]["document_title"] == "Churn Framework"


def test_build_insight_context_accepts_dict_knowledge_snippets():
    context = build_insight_context(
        research_goal="Understand churn drivers",
        statistical_findings=["Q3 top box dropped to 32%"],
        coded_themes=[{"theme_name": "Boredom", "count": 12}],
        knowledge_snippets=[
            {"document_title": "Churn Study", "content": "Boredom drives churn."}
        ],
    )
    assert "Churn Study" in context
    assert "Boredom" in context


def test_build_insight_markdown_appends_evidence_section():
    markdown = build_insight_markdown(
        llm_output="Boredom emerged as the dominant churn factor.",
        citations=[
            {"document_title": "Churn Framework", "content": "Boredom top driver."}
        ],
    )
    assert "## Evidence Basis" in markdown
    assert "Churn Framework" in markdown


def test_load_insight_prompt_contains_citation_instruction():
    prompt = load_insight_prompt()
    assert "citation" in prompt.lower() or "evidence" in prompt.lower()
```

**Step 2:** Run test to verify failure.

**Step 3: Implement**

- Create `models/insight.py` with `InsightRecord(SQLModel, table=True)`:
  - `analysis_run_id`, `narrative`, `evidence_section`, `citations` (JSON), `created_at`

- Upgrade `services/insights.py`:
  - `build_insight_context()` now accepts `list[str | dict]` for all inputs (backward compatible)
  - `build_insight_markdown()` appends `## Evidence Basis` section (mirrors 2C pattern)
  - `load_insight_prompt()` reads from expanded `insight_synthesis.md`
  - `synthesize_insights()` returns upgraded `InsightSynthesisResult` with structured fields

- Expand `llm/prompts/insight_synthesis.md` with structured contract:
  - Input: research goal, statistical findings, coded themes, knowledge snippets
  - Output: Markdown narrative with inline citations
  - Constraint: every claim must reference either a stat finding, a coded theme, or a knowledge source
  - Do not fabricate evidence

**Step 4:** Run test to verify pass. Existing `test_build_insight_context_includes_stats_and_knowledge` must also still pass (backward compatibility).

**Step 5:** Commit: `feat: upgrade insight synthesis with structured evidence`

---

### Task 6: Build insight synthesis orchestration with retrieval and persistence

**Files:**
- Modify: `src/game_survey_workbench/services/insights.py`
- Modify: `tests/test_insights_service.py`

**Step 1: Write the failing test**

```python
from game_survey_workbench.llm.client import FakeLLMClient
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.insights import generate_analysis_insights


def test_generate_analysis_insights_retrieves_knowledge_and_persists(tmp_path):
    source = tmp_path / "churn.md"
    source.write_text(
        "---\n"
        "title: Churn Framework\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - analysis\n"
        "scenario: churn\n"
        "---\n"
        "Boredom and difficulty are the top churn drivers.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)
    create_project(
        ProjectCreate(
            slug="churn-study",
            name="Churn Study",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["churn"]},
        ),
        workspace_root=tmp_path,
    )

    result = generate_analysis_insights(
        project_slug="churn-study",
        analysis_run_id="run-1",
        research_goal="Understand churn drivers",
        statistical_findings=["Top box dropped to 32%"],
        coded_themes=[{"theme_name": "Boredom", "count": 12}],
        workspace_root=tmp_path,
        client=FakeLLMClient("Boredom emerged as the dominant churn factor."),
    )

    assert "## Evidence Basis" in result.narrative
    assert result.citations[0]["document_title"] == "Churn Framework"
```

**Step 2:** Run test to verify failure.

**Step 3: Implement**

```python
def generate_analysis_insights(
    *,
    project_slug: str,
    analysis_run_id: str,
    research_goal: str,
    statistical_findings: list[str],
    coded_themes: list[str | dict],
    workspace_root: Path,
    client: LLMClient,
    top_k: int = 10,
) -> InsightRecord:
    snippets = retrieve_project_knowledge(
        workspace_root=workspace_root,
        project_slug=project_slug,
        query=research_goal,
        stages=["analysis"],
        top_k=top_k,
    )
    context = build_insight_context(...)
    prompt = load_insight_prompt()
    llm_output = client.generate(f"{prompt}\n\n{context}")
    narrative = build_insight_markdown(llm_output=llm_output, citations=snippets)
    result = InsightRecord(
        analysis_run_id=analysis_run_id,
        narrative=narrative,
        evidence_section=...,
        citations=snippets,
    )
    # Persist to database
    ...
    return result
```

**Step 4:** Run test to verify pass.

**Step 5:** Commit: `feat: orchestrate insight synthesis with retrieval and persistence`

---

### Task 7: Add routes for text coding and insight synthesis

**Files:**
- Create: `src/game_survey_workbench/routes/text_coding.py`
- Create: `src/game_survey_workbench/routes/insights.py`
- Modify: `src/game_survey_workbench/app.py` (register routers)
- Create: `tests/test_text_coding_routes.py`
- Create: `tests/test_insights_routes.py`

**Step 1: Write the failing tests**

```python
# test_text_coding_routes.py
def test_code_text_route_returns_themes(tmp_path, monkeypatch):
    # POST /projects/{slug}/analysis/{run_id}/code-text
    # Body: {"question_column": "...", "responses": [...]}
    # Returns: {"themes": [...], "citations": [...]}
    ...

# test_insights_routes.py
def test_generate_insights_route_returns_narrative(tmp_path, monkeypatch):
    # POST /projects/{slug}/analysis/{run_id}/insights
    # Body: {"research_goal": "...", "statistical_findings": [...], "coded_themes": [...]}
    # Returns: {"narrative": "...", "citations": [...]}
    ...
```

**Step 2:** Run test to verify failure.

**Step 3: Implement**

Route patterns:
- `POST /projects/{project_slug}/analysis/{analysis_run_id}/code-text` -> `text_coding.code_open_text_column()`
- `POST /projects/{project_slug}/analysis/{analysis_run_id}/insights` -> `insights.generate_analysis_insights()`

Error handling (follow 2C pattern but use custom exceptions instead of string matching):
- Project not found -> 404
- Analysis run not found -> 404
- No knowledge matched -> 400
- LLM not configured -> 500

**Step 4:** Run test to verify pass.

**Step 5:** Commit: `feat: add text coding and insight synthesis routes`

---

### Task 8: Integrate evidence into report generation

**Files:**
- Modify: `src/game_survey_workbench/services/reporting.py`
- Modify: `tests/test_reporting.py`

**Step 1: Write the failing test**

```python
def test_render_report_markdown_includes_evidence_basis_when_provided():
    markdown = render_report_markdown(
        title="Churn Report",
        summary_points=["Boredom is the top driver."],
        sections={"Key Findings": ["Top box dropped to 32%."]},
        evidence=[
            {"document_title": "Churn Framework", "content": "Boredom top driver."},
        ],
    )
    assert "## Evidence Basis" in markdown
    assert "Churn Framework" in markdown
```

**Step 2:** Run test to verify failure.

**Step 3: Implement**

- Add optional `evidence: list[dict] | None = None` parameter to `render_report_markdown()`
- Update the Jinja2 template `reports/report.md.j2` to render an `## Evidence Basis` section when evidence is provided
- Update `save_report()` to accept and forward evidence
- Keep backward compatible: no evidence = no section appended

**Step 4:** Run test to verify pass. Existing reporting tests must still pass.

**Step 5:** Commit: `feat: integrate evidence basis into report generation`

---

### Task 9: Harden error paths and add custom exception classes

**Files:**
- Create: `src/game_survey_workbench/errors.py`
- Modify: `src/game_survey_workbench/services/questionnaires.py` (use new exceptions)
- Modify: `src/game_survey_workbench/routes/questionnaires.py` (use new exceptions)
- Modify: routes for text coding and insights
- Modify: `tests/test_text_coding_service.py`
- Modify: `tests/test_insights_service.py`

**Step 1: Write the failing tests**

```python
import pytest
from game_survey_workbench.errors import ProjectNotFoundError, NoKnowledgeMatchedError


def test_code_open_text_rejects_missing_project(tmp_path):
    with pytest.raises(ProjectNotFoundError):
        code_open_text_column(
            project_slug="nonexistent",
            analysis_run_id="run-1",
            question_column="Q1",
            responses=["test"],
            workspace_root=tmp_path,
            client=FakeLLMClient("{}"),
        )


def test_generate_insights_rejects_missing_knowledge(tmp_path):
    # project exists but no knowledge ingested
    with pytest.raises(NoKnowledgeMatchedError):
        ...
```

**Step 2:** Run test to verify failure.

**Step 3: Implement**

```python
# errors.py
class ProjectNotFoundError(ValueError):
    pass

class NoKnowledgeMatchedError(ValueError):
    pass

class AnalysisRunNotFoundError(ValueError):
    pass
```

Update routes to catch these typed exceptions instead of matching on string content. Migrate the questionnaire route to use these exceptions as well (improving Finding #4 from the review).

**Step 4:** Run test to verify pass. Full suite must pass.

**Step 5:** Commit: `refactor: replace string-based error matching with typed exceptions`

---

### Task 10: End-to-end integration test

**Files:**
- Modify: `tests/test_end_to_end_smoke.py`

**Step 1: Write the failing test**

Extend the existing E2E test to exercise the full Stage 2D flow:

```python
def test_end_to_end_flow_with_text_coding_and_insights(client, seeded_workspace, monkeypatch):
    # 1. Create project + ingest knowledge
    # 2. Generate questionnaire draft (2C)
    # 3. Import dataset with free_text column
    # 4. Code open-text responses
    # 5. Generate insights from deterministic stats + coded themes + knowledge
    # 6. Generate report with evidence basis
    # Assert: report includes ## Evidence Basis
    # Assert: coding result has themes
    # Assert: insight narrative references knowledge
    ...
```

**Step 2:** Run test to verify failure.

**Step 3:** Wire up the route calls in sequence. Use monkeypatched LLM client for deterministic output.

**Step 4:** Run test to verify pass. Full suite must pass.

**Step 5:** Commit: `test: add end-to-end coverage for text coding and insight synthesis`

---

## Verification Checklist Before Any Implementation Claim

- Run: `.venv/Scripts/python.exe -m pytest -v`
- Run: `.venv/Scripts/python.exe -m compileall src`
- Manually confirm:
  - open-text coding produces themed output with knowledge citations
  - insight synthesis combines stats + themes + knowledge into a narrative
  - `## Evidence Basis` section appears in both insight output and final report
  - missing project, missing knowledge, and missing LLM config fail with typed exceptions
  - existing 2C questionnaire flow is unaffected

## Manual Acceptance Inputs

Use these real acceptance scenarios after implementation:

1. **Text coding scenario:** Import a dataset with a free-text column like "Why did you stop playing?", ingest a knowledge document about churn drivers, run text coding, verify themes are grounded in knowledge.

2. **Insight synthesis scenario:** After coding, feed deterministic stats (e.g., "satisfaction top box dropped to 32%") plus coded themes into insight synthesis, verify the narrative references both the stat and the knowledge source.

3. **Report with evidence:** Generate a report from an analysis run that has both coded themes and synthesized insights, verify the `## Evidence Basis` section is present and traceable.

## Risks and Notes

- Do not skip retrieval by hardcoding knowledge in the coding or insight layers
- Keep the LLM response parsing defensive — open-text coding expects JSON output from the LLM, which may be malformed. Always wrap in try/except with a clear fallback
- Do not change the questionnaire grounding flow (Stage 2C)
- Do not introduce embedding retrieval upgrades in this stage
- The `top_k` parameter added in Task 2 is critical for keeping prompt size bounded as response lists can be large
- Consider sampling responses (e.g., max 100) before sending to LLM to avoid token limits
- Deterministic analytics remain untouched — LLM interpretation is additive, not a replacement
