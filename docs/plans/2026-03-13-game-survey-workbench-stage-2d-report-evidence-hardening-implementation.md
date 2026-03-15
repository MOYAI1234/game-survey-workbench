# Game Survey Workbench Stage 2D Report Evidence Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the Stage 2D closeout by binding analysis-side LLM workflows to persisted run data, failing clearly on malformed coding output, and tightening report evidence flow so saved artifacts remain reproducible and inspectable.

**Architecture:** Keep the current local monolith and reuse the existing Stage 2A-2D retrieval, questionnaire, coding, insight, and reporting layers. Add a small analysis-context layer that loads deterministic inputs from `analysis_run_id`, move coding and insight routes to consume those persisted inputs instead of trusting request bodies, and make report generation consume structured insight fields instead of embedding pre-rendered markdown inside list items.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, pytest, pandas, Jinja2

---

## Relationship to Current Plans

This plan is the direct follow-up to:

- `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`
- `docs/plans/2026-03-13-game-survey-workbench-stage-2-llm-knowledge-plan.md`
- `docs/plans/2026-03-13-game-survey-workbench-stage-2d-open-text-coding-and-insight-synthesis-implementation.md`

It stays inside Stage 2 and does **not** introduce Stage 3 context-layer work.

It specifically addresses the current Stage 2D review findings:

1. analysis endpoints are not yet bound to persisted run inputs
2. malformed coding output is silently persisted as a successful result
3. report generation duplicates and mis-nests evidence markdown

## Why This Plan Comes Next

Stage 2D added the analysis-side LLM workflows, but the current implementation is still only partially aligned with the north-star loop:

`Knowledge Base -> Questionnaire Design -> Data Analysis -> Markdown Report`

The main remaining gap is that `Data Analysis` and `Markdown Report` are not yet fully driven by saved run artifacts:

- text coding still accepts raw responses from the client
- insight synthesis still accepts statistical findings and coded themes from the client
- report generation still embeds saved insight markdown in a way that duplicates evidence structure
- malformed coding output can be stored as if it were a valid analytical result

This plan closes those gaps without changing product direction.

## Success Criteria

This follow-up is complete when:

- text coding loads free-text responses from the persisted dataset referenced by `analysis_run_id`
- insight synthesis loads deterministic findings and saved coding themes from persisted analysis artifacts
- malformed coding output fails clearly with a typed exception and is not saved as a successful coding result
- reports render saved insight narrative and saved evidence as separate structured sections
- the end-to-end flow from dataset import to report generation is reproducible from stored artifacts instead of request-body reconstruction

## Non-Goals

- no Stage 3 Research Brief or Task Plan work
- no retrieval pipeline redesign
- no embedding model changes
- no dashboard / BI / multi-user expansion
- no attempt to generalize the product beyond game survey research

---

## Task 1: Add persisted analysis-run context loading helpers

**Files:**
- Create: `src/game_survey_workbench/services/analysis_context.py`
- Modify: `src/game_survey_workbench/services/dataset_import.py`
- Modify: `src/game_survey_workbench/models/dataset.py`
- Modify: `src/game_survey_workbench/models/analysis_run.py`
- Create: `tests/test_analysis_context.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.analysis_context import (
    load_analysis_run_context,
    load_free_text_responses_for_question,
)
from game_survey_workbench.services.dataset_import import import_dataset
from game_survey_workbench.services.projects import create_project


def test_load_analysis_run_context_returns_dataset_schema_and_source_path(tmp_path: Path):
    create_project(
        ProjectCreate(slug="demo", name="Demo", knowledge_pack={}),
        workspace_root=tmp_path,
    )
    dataset_path = tmp_path / "survey.csv"
    dataset_path.write_text(
        "Q1,Q1_other,Q2\n"
        "single_choice,free_text,scale\n"
        "A,too hard,5\n",
        encoding="utf-8",
    )
    imported = import_dataset(dataset_path, project_slug="demo", workspace_root=tmp_path)

    context = load_analysis_run_context(
        analysis_run_id=imported.analysis_run_id,
        workspace_root=tmp_path,
    )

    assert context.dataset_record.dataset_id == imported.dataset_id
    assert "Q1" in context.dataset_record.dataset_schema


def test_load_free_text_responses_for_question_uses_other_text_link_when_present(tmp_path: Path):
    create_project(
        ProjectCreate(slug="demo", name="Demo", knowledge_pack={}),
        workspace_root=tmp_path,
    )
    dataset_path = tmp_path / "survey.csv"
    dataset_path.write_text(
        "Why did you leave?,Why did you leave?_other\n"
        "single_choice,free_text\n"
        "Other,too hard\n"
        "Other,got bored\n",
        encoding="utf-8",
    )
    imported = import_dataset(dataset_path, project_slug="demo", workspace_root=tmp_path)

    responses = load_free_text_responses_for_question(
        analysis_run_id=imported.analysis_run_id,
        question_column="Why did you leave?",
        workspace_root=tmp_path,
    )

    assert responses == ["too hard", "got bored"]
```

**Step 2: Run tests to verify failure**

Run: `.venv/Scripts/python.exe -m pytest -v tests/test_analysis_context.py`

Expected:
- FAIL because `analysis_context.py` does not exist yet

**Step 3: Write the minimal implementation**

Create an analysis-context helper module with:

```python
@dataclass
class AnalysisRunContext:
    analysis_run: AnalysisRunRecord
    dataset_record: DatasetRecord
    dataframe: pd.DataFrame


def load_analysis_run_context(*, analysis_run_id: str, workspace_root: Path) -> AnalysisRunContext:
    ...


def load_free_text_responses_for_question(
    *,
    analysis_run_id: str,
    question_column: str,
    workspace_root: Path,
) -> list[str]:
    ...
```

Implementation notes:

- use `AnalysisRunRecord.dataset_id` to locate the persisted `DatasetRecord`
- use `DatasetRecord.source_path` to load the original CSV/XLSX file
- reuse `dataset_import._load_tabular_file()` instead of duplicating format logic
- if `QuestionColumnSchema.other_text_column` exists, load that linked free-text column
- otherwise load the direct free-text column
- add a typed exception if the run or question is invalid

**Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python.exe -m pytest -v tests/test_analysis_context.py`

Expected:
- PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/analysis_context.py src/game_survey_workbench/services/dataset_import.py src/game_survey_workbench/models/dataset.py src/game_survey_workbench/models/analysis_run.py tests/test_analysis_context.py
git commit -m "feat: add persisted analysis run context helpers"
```

---

## Task 2: Bind text coding to persisted run inputs

**Files:**
- Modify: `src/game_survey_workbench/routes/text_coding.py`
- Modify: `src/game_survey_workbench/models/text_coding.py`
- Modify: `src/game_survey_workbench/services/text_coding.py`
- Modify: `src/game_survey_workbench/services/analysis_context.py`
- Modify: `tests/test_text_coding_routes.py`
- Modify: `tests/test_text_coding_service.py`

**Step 1: Write the failing tests**

```python
def test_code_text_route_ignores_client_supplied_responses_and_uses_saved_run_data(tmp_path, monkeypatch):
    ...
    response = client.post(
        f"/projects/churn-study/analysis/{analysis_run_id}/code-text",
        json={
            "question_column": "Why did you leave?",
            "responses": ["fake client value"],
        },
    )
    payload = response.json()
    assert payload["themes"][0]["count"] == 2


def test_code_open_text_column_uses_loaded_run_responses_when_route_calls_it(tmp_path):
    ...
```

**Step 2: Run tests to verify failure**

Run: `.venv/Scripts/python.exe -m pytest -v tests/test_text_coding_routes.py tests/test_text_coding_service.py`

Expected:
- FAIL because route still forwards raw `payload.responses`

**Step 3: Write the minimal implementation**

Changes:

- make `TextCodingRequest.responses` optional for backward compatibility, then stop using it in the route
- in `routes/text_coding.py`, load responses via `load_free_text_responses_for_question()`
- keep `code_open_text_column()` response contract unchanged
- if no persisted responses are found for the question, raise a typed error instead of saving an empty coding result

Use this shape in the route:

```python
responses = load_free_text_responses_for_question(
    analysis_run_id=analysis_run_id,
    question_column=payload.question_column,
    workspace_root=settings.workspace_root,
)
result = code_open_text_column(..., responses=responses, ...)
```

**Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python.exe -m pytest -v tests/test_text_coding_routes.py tests/test_text_coding_service.py`

Expected:
- PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/text_coding.py src/game_survey_workbench/models/text_coding.py src/game_survey_workbench/services/text_coding.py src/game_survey_workbench/services/analysis_context.py tests/test_text_coding_routes.py tests/test_text_coding_service.py
git commit -m "feat: bind text coding to persisted analysis inputs"
```

---

## Task 3: Fail clearly on malformed coding output

**Files:**
- Modify: `src/game_survey_workbench/errors.py`
- Modify: `src/game_survey_workbench/services/text_coding.py`
- Modify: `src/game_survey_workbench/routes/text_coding.py`
- Modify: `tests/test_text_coding_service.py`
- Modify: `tests/test_text_coding_routes.py`

**Step 1: Write the failing tests**

```python
import pytest

from game_survey_workbench.errors import CodingResponseFormatError
from game_survey_workbench.llm.client import FakeLLMClient


def test_parse_coding_response_raises_typed_error_on_invalid_json():
    with pytest.raises(CodingResponseFormatError):
        parse_coding_response("not-json")


def test_code_open_text_column_does_not_persist_invalid_llm_output(tmp_path):
    ...
    with pytest.raises(CodingResponseFormatError):
        code_open_text_column(..., client=FakeLLMClient("not-json"))
    assert session.exec(select(CodingResult)).all() == []


def test_code_text_route_returns_500_for_invalid_coding_output(tmp_path, monkeypatch):
    ...
    assert response.status_code == 500
```

**Step 2: Run tests to verify failure**

Run: `.venv/Scripts/python.exe -m pytest -v tests/test_text_coding_service.py tests/test_text_coding_routes.py`

Expected:
- FAIL because invalid JSON is still converted into a fake successful result

**Step 3: Write the minimal implementation**

Add a new typed error:

```python
class CodingResponseFormatError(ValueError):
    pass
```

Update `parse_coding_response()`:

- raise `CodingResponseFormatError` on invalid JSON
- raise `CodingResponseFormatError` if `themes` is not a list
- raise `CodingResponseFormatError` if any required theme fields are missing or malformed

Update the route:

- map `CodingResponseFormatError` to HTTP 500
- do not save any `CodingResult` when parsing fails

**Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python.exe -m pytest -v tests/test_text_coding_service.py tests/test_text_coding_routes.py`

Expected:
- PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/errors.py src/game_survey_workbench/services/text_coding.py src/game_survey_workbench/routes/text_coding.py tests/test_text_coding_service.py tests/test_text_coding_routes.py
git commit -m "fix: reject malformed coding output"
```

---

## Task 4: Bind insight synthesis to persisted deterministic findings and saved coding results

**Files:**
- Modify: `src/game_survey_workbench/services/analysis_context.py`
- Modify: `src/game_survey_workbench/services/analytics.py`
- Modify: `src/game_survey_workbench/routes/insights.py`
- Modify: `src/game_survey_workbench/services/insights.py`
- Modify: `src/game_survey_workbench/models/insight.py`
- Modify: `tests/test_insights_routes.py`
- Modify: `tests/test_insights_service.py`

**Step 1: Write the failing tests**

```python
def test_generate_insights_route_uses_saved_coding_results_and_run_findings(tmp_path, monkeypatch):
    ...
    client.post(f"/projects/{slug}/analysis/{run_id}/code-text", json={"question_column": "Why did you leave?"})
    response = client.post(
        f"/projects/{slug}/analysis/{run_id}/insights",
        json={"research_goal": "Understand churn drivers"},
    )
    payload = response.json()
    assert "Top box" in payload["narrative"] or "Boredom" in payload["narrative"]


def test_generate_analysis_insights_rejects_missing_saved_coding_results(tmp_path):
    ...
```

**Step 2: Run tests to verify failure**

Run: `.venv/Scripts/python.exe -m pytest -v tests/test_insights_routes.py tests/test_insights_service.py`

Expected:
- FAIL because route still trusts request-body `statistical_findings` and `coded_themes`

**Step 3: Write the minimal implementation**

Add persisted run helpers to `analysis_context.py`:

```python
def build_deterministic_findings_for_run(*, analysis_run_id: str, workspace_root: Path) -> list[str]:
    ...


def load_saved_coding_themes(*, analysis_run_id: str, workspace_root: Path) -> list[dict]:
    ...
```

Implementation rules:

- compute deterministic findings from the stored dataset and schema, not from the request
- load coded themes from saved `CodingResult` rows for that run
- keep `research_goal` as a route input for now, since project-level persisted briefing does not exist yet
- reject insight generation if there are no saved coding results for that run

Update the route to call:

```python
statistical_findings = build_deterministic_findings_for_run(...)
coded_themes = load_saved_coding_themes(...)
result = generate_analysis_insights(..., statistical_findings=statistical_findings, coded_themes=coded_themes, ...)
```

**Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python.exe -m pytest -v tests/test_insights_routes.py tests/test_insights_service.py`

Expected:
- PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/analysis_context.py src/game_survey_workbench/services/analytics.py src/game_survey_workbench/routes/insights.py src/game_survey_workbench/services/insights.py src/game_survey_workbench/models/insight.py tests/test_insights_routes.py tests/test_insights_service.py
git commit -m "feat: bind insights to saved run analysis artifacts"
```

---

## Task 5: Separate report narrative rendering from evidence rendering

**Files:**
- Modify: `src/game_survey_workbench/services/insights.py`
- Modify: `src/game_survey_workbench/routes/reports.py`
- Modify: `src/game_survey_workbench/services/reporting.py`
- Modify: `src/game_survey_workbench/templates/reports/report.md.j2`
- Modify: `tests/test_reporting.py`
- Modify: `tests/test_end_to_end_smoke.py`

**Step 1: Write the failing tests**

```python
def test_generate_report_renders_saved_insight_narrative_without_bullet_wrapping(tmp_path, monkeypatch):
    ...
    markdown = report_path.read_text(encoding="utf-8")
    assert "## Key Findings" in markdown
    assert "\n- Boredom emerged" not in markdown
    assert markdown.count("## Evidence Basis") == 1


def test_build_insight_markdown_keeps_narrative_and_evidence_separate():
    result = synthesize_insights(...)
    assert "## Evidence Basis" not in result.narrative
    assert result.evidence_section.startswith("## Evidence Basis")
```

**Step 2: Run tests to verify failure**

Run: `.venv/Scripts/python.exe -m pytest -v tests/test_reporting.py tests/test_insights_service.py tests/test_end_to_end_smoke.py`

Expected:
- FAIL because insight narrative currently includes evidence markdown and report template bullet-wraps it

**Step 3: Write the minimal implementation**

Refactor insight/report contracts:

- change `InsightRecord.narrative` to store narrative-only markdown
- keep `evidence_section` as the saved evidence block
- update `synthesize_insights()` so `result.narrative` is the pure LLM narrative and `result.evidence_section` is generated separately
- update `generate_analysis_insights()` and route responses to expose both fields
- update `render_report_markdown()` and `report.md.j2` to support a narrative block, for example:

```python
render_report_markdown(
    title=...,
    summary_points=...,
    sections=...,
    narrative="...",
    evidence=[...],
)
```

Template rule:

- render narrative as plain markdown text under `## Key Findings`
- render `## Evidence Basis` exactly once at report level

**Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python.exe -m pytest -v tests/test_reporting.py tests/test_insights_service.py tests/test_end_to_end_smoke.py`

Expected:
- PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/insights.py src/game_survey_workbench/routes/reports.py src/game_survey_workbench/services/reporting.py src/game_survey_workbench/templates/reports/report.md.j2 tests/test_reporting.py tests/test_end_to_end_smoke.py
git commit -m "feat: render report narrative and evidence separately"
```

---

## Task 6: Full regression and acceptance coverage for persisted evidence flow

**Files:**
- Modify: `tests/test_end_to_end_smoke.py`
- Modify: `tests/test_errors.py`
- Modify: `tests/test_reporting.py`

**Step 1: Write the failing tests**

Extend the end-to-end coverage so the full run is artifact-driven:

```python
def test_end_to_end_flow_rebuilds_report_from_saved_run_artifacts(client, seeded_workspace, monkeypatch):
    # 1. ingest knowledge
    # 2. create project
    # 3. import dataset
    # 4. code text using only analysis_run_id + question_column
    # 5. synthesize insights using only analysis_run_id + research_goal
    # 6. generate report from saved run
    # Assert: report contains single Evidence Basis section
    # Assert: report does not depend on client-supplied raw responses
```

Add regression checks for:

- malformed coding output returns an explicit error and saves no result
- insight generation fails if there are no saved coding results
- report generation continues to work when no Stage 2D artifacts exist yet

**Step 2: Run tests to verify failure**

Run: `.venv/Scripts/python.exe -m pytest -v tests/test_end_to_end_smoke.py tests/test_errors.py tests/test_reporting.py`

Expected:
- FAIL until all artifact-driven behavior is wired correctly

**Step 3: Write the minimal implementation**

Only fill implementation gaps required by the failing tests.

Do not add:

- Stage 3 project-brief features
- new UI flows
- non-essential refactors outside analysis/report evidence flow

**Step 4: Run full verification**

Run:

```bash
.venv/Scripts/python.exe -m pytest -v
.venv/Scripts/python.exe -m compileall src
```

Expected:
- full suite passes
- compileall succeeds

**Step 5: Commit**

```bash
git add tests/test_end_to_end_smoke.py tests/test_errors.py tests/test_reporting.py
git commit -m "test: harden persisted analysis evidence flow"
```

---

## Verification Checklist Before Any Implementation Claim

- Run: `.venv/Scripts/python.exe -m pytest -v`
- Run: `.venv/Scripts/python.exe -m compileall src`
- Manually confirm:
  - `code-text` works when given only `analysis_run_id` + `question_column`
  - `insights` works when given only persisted run artifacts plus `research_goal`
  - malformed coding output does not create a successful `CodingResult`
  - final report contains one `## Evidence Basis` section
  - report content is reconstructed from saved artifacts rather than ad hoc request payloads
  - Stage 2C questionnaire generation still behaves the same as before

## Manual Acceptance Inputs

Use these after implementation:

1. **Run-bound coding check:** import a real survey with an `other_text` or free-text column, trigger coding from the run without manually supplying responses, and verify the saved output reflects the actual stored data.

2. **Run-bound insight check:** trigger insight synthesis from the same run after coding, and verify the narrative references persisted coded themes plus deterministic findings from the stored dataset.

3. **Report evidence check:** generate the report after insight synthesis and confirm the report shows one clean evidence section, with no duplicated `## Evidence Basis` block and no markdown headings nested inside bullets.

## User Support Needed Before Implementation

The engineer implementing this plan will move faster if the product owner can provide:

- one realistic open-text survey file that includes `free_text` and/or `other_text_column` patterns
- one realistic knowledge document that should meaningfully influence coding and insights
- one example of what a “good enough” final Markdown report narrative should look like
- a decision on malformed LLM coding output:
  - preferred default: fail the request and save nothing
  - alternative: persist a `needs_review` state in a later phase

## Notes

- This plan intentionally stays inside Stage 2 and does not start Stage 3
- If implementation reveals that deterministic findings need a separate persistence model, stop and write that gap down before expanding scope
- Prefer route simplification over adding more client-controlled analytical inputs
- Keep TDD and frequent commits exactly as in earlier Stage 2 work
