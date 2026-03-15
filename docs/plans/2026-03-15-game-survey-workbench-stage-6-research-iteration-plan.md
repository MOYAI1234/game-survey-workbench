# Stage 6: Research Iteration & Workflow Intelligence — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the workbench from a one-shot generation tool into an iterative research environment where questionnaires, coding, and insights improve through revision cycles, and where workflow state is explicit and failures are surfaced — not swallowed.

**Architecture:** Add a lightweight workflow state machine to `AnalysisRunRecord`, version-aware comparison endpoints for questionnaire and insight outputs, structured error responses for browser form routes, and retrieval relevance improvements using TF-IDF weighting. All changes extend existing models and services — no new frameworks, no new dependencies.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLModel, pandas, pytest, httpx/TestClient (all existing). No new dependencies.

**North-star alignment:** The north-star core loop is `Knowledge Base → Questionnaire Design → Data Analysis → Markdown Report`. Stage 5 made this loop accessible in the browser. Stage 6 makes it *repeatable and improvable* — a researcher can now iterate on outputs, see what changed, understand what failed, and accumulate better knowledge across runs. This directly serves north-star priority #1: "Prefer work that strengthens the core loop over shell polish."

**Prerequisite state:** Stage 5 merged to master, ~160 tests passing. Full browser workflow operational (project creation → brief → knowledge upload → dataset import → analysis → coding → insights → questionnaire → report).

---

## Stage 5 Closeout Assessment

### What Stage 5 delivered

| Sub-stage | Capability | Status |
|-----------|-----------|--------|
| 5A | Browser project creation form, brief editing, knowledge upload, dataset import | ✓ |
| 5B | Analysis dashboard with schema/findings/coding/insight display | ✓ |
| 5B | Questionnaire detail page with latest spec display | ✓ |
| 5C | Form-triggered text coding, insight generation, report generation | ✓ |
| 5C | Report detail page with markdown content view | ✓ |
| 5 nav | Top-level navigation bar across all pages | ✓ |

### What Stage 5 left incomplete

These are the gaps that inform Stage 6 scope:

1. **No iteration capability** — every LLM action is one-shot; no way to re-draft a questionnaire with feedback, re-run coding with adjusted parameters, or regenerate insights with a different research goal
2. **Silent error handling** — browser form routes catch exceptions with bare `pass`; the user sees a redirect but has no idea if the operation succeeded or failed
3. **No workflow state** — `AnalysisRunRecord.status` exists but is always `"ready"`; no tracking of what steps have been completed (coded? insights generated? report generated?)
4. **No version comparison** — `QuestionnaireSpecVersion` has `version_id` and multiple versions can be saved, but only `latest` is displayed; no way to compare drafts
5. **Keyword-only retrieval** — `LocalVectorStore.query()` uses simple term-frequency matching; relevant knowledge documents with different phrasing are missed entirely

### Why Stage 6, not polish

The missing capabilities above are not cosmetic — they directly limit whether a researcher can complete a real research project using the workbench:

- Without iteration, the researcher must accept the first LLM output or start over
- Without error feedback, the researcher cannot diagnose why an operation produced nothing
- Without workflow state, the researcher loses track of progress across sessions
- Without version comparison, iterative improvement has no visibility

These are **core loop quality gaps**, not shell polish. The north-star says: "Prefer work that strengthens the core loop over shell polish."

### Non-goals for Stage 6

- No frontend framework migration (stays Jinja2 + vanilla JS)
- No semantic embedding model (retrieval improves via TF-IDF, not vector embeddings)
- No multi-user features
- No visual chart/dashboard components
- No questionnaire distribution or response collection
- No PDF/Word export (Markdown remains the output format)
- No mobile-responsive redesign

---

## Task Breakdown

### Task 1: Analysis Workflow State Machine

**Why first:** Every subsequent task (iteration, error display, re-run) depends on knowing what state the analysis is in. This is the foundation.

**Files:**
- Modify: `src/game_survey_workbench/models/analysis_run.py`
- Create: `src/game_survey_workbench/services/workflow_state.py`
- Test: `tests/test_stage6a_workflow_state.py`

**Step 1: Write the failing test**

```python
# tests/test_stage6a_workflow_state.py
"""Workflow state machine for analysis runs."""
import pytest
from game_survey_workbench.services.workflow_state import (
    WorkflowState,
    advance_workflow,
    get_workflow_state,
)


def test_initial_state_is_imported():
    state = WorkflowState()
    assert state.current_phase == "imported"
    assert state.completed_phases == []


def test_advance_after_coding():
    state = WorkflowState()
    state = advance_workflow(state, "coding_complete")
    assert state.current_phase == "coded"
    assert "coding_complete" in state.completed_phases


def test_advance_after_insights():
    state = WorkflowState(current_phase="coded", completed_phases=["coding_complete"])
    state = advance_workflow(state, "insights_complete")
    assert state.current_phase == "insights_ready"
    assert "insights_complete" in state.completed_phases


def test_advance_after_report():
    state = WorkflowState(
        current_phase="insights_ready",
        completed_phases=["coding_complete", "insights_complete"],
    )
    state = advance_workflow(state, "report_complete")
    assert state.current_phase == "report_generated"


def test_record_failure():
    state = WorkflowState()
    state = advance_workflow(state, "coding_failed", error="LLM timeout")
    assert state.current_phase == "imported"  # stays in same phase
    assert state.last_error == "LLM timeout"


def test_re_run_clears_error():
    state = WorkflowState(current_phase="imported", last_error="previous failure")
    state = advance_workflow(state, "coding_complete")
    assert state.last_error is None


def test_serialize_roundtrip():
    state = WorkflowState(
        current_phase="coded",
        completed_phases=["coding_complete"],
        last_error=None,
    )
    data = state.to_dict()
    restored = WorkflowState.from_dict(data)
    assert restored.current_phase == state.current_phase
    assert restored.completed_phases == state.completed_phases
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stage6a_workflow_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'game_survey_workbench.services.workflow_state'`

**Step 3: Write minimal implementation**

```python
# src/game_survey_workbench/services/workflow_state.py
"""Lightweight workflow state machine for analysis runs.

Phases: imported -> coded -> insights_ready -> report_generated
Each phase transition is triggered by an event string.
Failures record the error but do not advance the phase.
"""
from __future__ import annotations

from dataclasses import dataclass, field


_TRANSITIONS: dict[str, tuple[str, str]] = {
    # event -> (required_current_phase_or_any, next_phase)
    "coding_complete": ("imported", "coded"),
    "insights_complete": ("coded", "insights_ready"),
    "report_complete": ("insights_ready", "report_generated"),
}

_FAILURE_EVENTS = {"coding_failed", "insights_failed", "report_failed"}


@dataclass
class WorkflowState:
    current_phase: str = "imported"
    completed_phases: list[str] = field(default_factory=list)
    last_error: str | None = None

    def to_dict(self) -> dict:
        return {
            "current_phase": self.current_phase,
            "completed_phases": list(self.completed_phases),
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> WorkflowState:
        return cls(
            current_phase=data.get("current_phase", "imported"),
            completed_phases=list(data.get("completed_phases", [])),
            last_error=data.get("last_error"),
        )


def get_workflow_state(workflow_json: dict | None) -> WorkflowState:
    """Load workflow state from a persisted JSON dict."""
    if workflow_json is None:
        return WorkflowState()
    return WorkflowState.from_dict(workflow_json)


def advance_workflow(
    state: WorkflowState,
    event: str,
    *,
    error: str | None = None,
) -> WorkflowState:
    """Apply an event to the workflow state and return the new state."""
    if event in _FAILURE_EVENTS:
        return WorkflowState(
            current_phase=state.current_phase,
            completed_phases=list(state.completed_phases),
            last_error=error,
        )

    transition = _TRANSITIONS.get(event)
    if transition is None:
        return state

    _required_phase, next_phase = transition
    new_completed = list(state.completed_phases)
    if event not in new_completed:
        new_completed.append(event)

    return WorkflowState(
        current_phase=next_phase,
        completed_phases=new_completed,
        last_error=None,
    )
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_stage6a_workflow_state.py -v`
Expected: 7 passed

**Step 5: Add workflow_state column to AnalysisRunRecord**

```python
# In src/game_survey_workbench/models/analysis_run.py
# Add to AnalysisRunRecord class:
    workflow_state: dict = Field(default_factory=dict, sa_column=Column(JSON, default={}))
```

The column stores `WorkflowState.to_dict()` output. Existing rows get `{}` which `get_workflow_state()` treats as initial state.

**Step 6: Write integration test for workflow persistence**

```python
# Add to tests/test_stage6a_workflow_state.py

from game_survey_workbench.models.analysis_run import AnalysisRunRecord
from game_survey_workbench.db import create_db_and_tables
from sqlmodel import Session, create_engine


def test_workflow_state_persists_on_analysis_run(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    create_db_and_tables(tmp_path)
    run = AnalysisRunRecord(
        analysis_run_id="run-wf-1",
        project_slug="proj",
        dataset_id="ds-1",
    )
    state = WorkflowState()
    state = advance_workflow(state, "coding_complete")
    run.workflow_state = state.to_dict()
    with Session(engine) as session:
        session.add(run)
        session.commit()
        session.refresh(run)
        loaded = get_workflow_state(run.workflow_state)
        assert loaded.current_phase == "coded"
```

**Step 7: Run all tests**

Run: `python -m pytest tests/test_stage6a_workflow_state.py -v`
Expected: 8 passed

**Step 8: Commit**

```bash
git add src/game_survey_workbench/services/workflow_state.py \
        src/game_survey_workbench/models/analysis_run.py \
        tests/test_stage6a_workflow_state.py
git commit -m "feat(stage6a): add analysis workflow state machine"
```

---

### Task 2: Wire Workflow State into Coding / Insights / Report Routes

**Why now:** With the state machine in place, the existing form routes need to advance workflow state on success and record errors on failure — replacing the current silent `pass` pattern.

**Files:**
- Modify: `src/game_survey_workbench/routes/text_coding.py`
- Modify: `src/game_survey_workbench/routes/insights.py`
- Modify: `src/game_survey_workbench/routes/reports.py`
- Modify: `src/game_survey_workbench/routes/datasets.py` (analysis detail template context)
- Test: `tests/test_stage6a_workflow_wiring.py`

**Step 1: Write the failing test**

```python
# tests/test_stage6a_workflow_wiring.py
"""Verify that form routes advance workflow state."""
import pytest
from fastapi.testclient import TestClient
from game_survey_workbench.app import create_app
from game_survey_workbench.services.workflow_state import get_workflow_state


@pytest.fixture
def client(tmp_path):
    app = create_app(workspace_root=tmp_path)
    return TestClient(app, follow_redirects=False)


def _setup_project_with_dataset(client, tmp_path):
    """Helper: create project + import dataset so we have an analysis run."""
    client.post("/projects", json={"slug": "wf-test", "name": "WF Test"})
    # Create a minimal CSV for import
    csv_path = tmp_path / "test.csv"
    csv_path.write_text("Q1,Q2\nsingle_choice,free_text\nA,hello\nB,world\n")
    with open(csv_path, "rb") as f:
        resp = client.post(
            "/projects/wf-test/datasets/import",
            files={"file": ("test.csv", f, "text/csv")},
        )
    data = resp.json()
    return data.get("analysis_run_id") or data.get("dataset_id")


def test_coding_advances_workflow_state(client, tmp_path):
    run_id = _setup_project_with_dataset(client, tmp_path)
    # Trigger text coding via form route
    resp = client.post(
        f"/projects/wf-test/analysis/{run_id}/code-text-all",
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    # Check workflow state was advanced
    detail = client.get(f"/projects/wf-test/analysis/{run_id}")
    # The analysis detail context should include workflow_state
    assert detail.status_code == 200


def test_analysis_detail_shows_workflow_phase(client, tmp_path):
    run_id = _setup_project_with_dataset(client, tmp_path)
    resp = client.get(f"/projects/wf-test/analysis/{run_id}")
    assert resp.status_code == 200
    assert b"imported" in resp.content or b"workflow" in resp.content.lower()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stage6a_workflow_wiring.py -v`
Expected: FAIL — workflow_state not wired into routes yet

**Step 3: Modify routes to advance workflow state**

In `src/game_survey_workbench/routes/text_coding.py`, after successful coding:
```python
from game_survey_workbench.services.workflow_state import advance_workflow, get_workflow_state

# After coding completes successfully in the code-text-all route:
run_record = session.get(AnalysisRunRecord, ...)
state = get_workflow_state(run_record.workflow_state)
state = advance_workflow(state, "coding_complete")
run_record.workflow_state = state.to_dict()
session.add(run_record)
session.commit()
```

In the `except` block, replace bare `pass` with:
```python
state = get_workflow_state(run_record.workflow_state)
state = advance_workflow(state, "coding_failed", error=str(e))
run_record.workflow_state = state.to_dict()
session.add(run_record)
session.commit()
```

Apply the same pattern to `insights.py` (`insights_complete` / `insights_failed`) and `reports.py` (`report_complete` / `report_failed`).

**Step 4: Pass workflow state to analysis detail template**

In `src/game_survey_workbench/routes/datasets.py`, when rendering the analysis detail page, add to template context:
```python
from game_survey_workbench.services.workflow_state import get_workflow_state

workflow = get_workflow_state(run_record.workflow_state)
context["workflow_phase"] = workflow.current_phase
context["workflow_error"] = workflow.last_error
context["workflow_completed"] = workflow.completed_phases
```

**Step 5: Run tests**

Run: `python -m pytest tests/test_stage6a_workflow_wiring.py -v`
Expected: PASS

**Step 6: Run full test suite**

Run: `python -m pytest --tb=short -q`
Expected: All passing (no regression)

**Step 7: Commit**

```bash
git add src/game_survey_workbench/routes/text_coding.py \
        src/game_survey_workbench/routes/insights.py \
        src/game_survey_workbench/routes/reports.py \
        src/game_survey_workbench/routes/datasets.py \
        tests/test_stage6a_workflow_wiring.py
git commit -m "feat(stage6a): wire workflow state into coding/insights/report routes"
```

---

### Task 3: Error Feedback in Browser Forms

**Why now:** With workflow state tracking failures, the UI needs to display them. Currently errors are swallowed — the user sees a redirect to the same page with no indication of what happened.

**Files:**
- Modify: `src/game_survey_workbench/routes/datasets.py` (analysis detail)
- Modify: `src/game_survey_workbench/templates/analysis/detail.html`
- Test: `tests/test_stage6b_error_feedback.py`

**Step 1: Write the failing test**

```python
# tests/test_stage6b_error_feedback.py
"""Verify that workflow errors are displayed in the browser UI."""
import pytest
from fastapi.testclient import TestClient
from game_survey_workbench.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(workspace_root=tmp_path)
    return TestClient(app)


def test_error_message_shown_on_analysis_page(client, tmp_path):
    """When workflow has a recorded error, the analysis page should show it."""
    from sqlmodel import Session
    from game_survey_workbench.models.analysis_run import AnalysisRunRecord
    from game_survey_workbench.services.workflow_state import (
        WorkflowState,
        advance_workflow,
    )

    client.post("/projects", json={"slug": "err-proj", "name": "Err"})
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("Q1\nsingle_choice\nA\nB\n")
    with open(csv_path, "rb") as f:
        resp = client.post(
            "/projects/err-proj/datasets/import",
            files={"file": ("data.csv", f, "text/csv")},
        )
    run_id = resp.json().get("analysis_run_id")

    # Manually set an error state
    from game_survey_workbench.db import get_engine
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        from sqlmodel import select
        run = session.exec(
            select(AnalysisRunRecord).where(
                AnalysisRunRecord.analysis_run_id == run_id
            )
        ).first()
        state = WorkflowState()
        state = advance_workflow(state, "coding_failed", error="LLM provider unreachable")
        run.workflow_state = state.to_dict()
        session.add(run)
        session.commit()

    resp = client.get(f"/projects/err-proj/analysis/{run_id}")
    assert resp.status_code == 200
    assert b"LLM provider unreachable" in resp.content


def test_success_clears_previous_error(client, tmp_path):
    """After a successful re-run, error should no longer appear."""
    # This tests that advance_workflow("coding_complete") clears last_error
    from game_survey_workbench.services.workflow_state import (
        WorkflowState,
        advance_workflow,
    )

    state = WorkflowState(last_error="old failure")
    state = advance_workflow(state, "coding_complete")
    assert state.last_error is None
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stage6b_error_feedback.py -v`
Expected: FAIL — error message not rendered in template

**Step 3: Update analysis detail template**

In `src/game_survey_workbench/templates/analysis/detail.html`, add near the top of the content area:

```html
{% if workflow_error %}
<div class="alert alert-error">
  <strong>Last operation failed:</strong> {{ workflow_error }}
  <p>You can retry the operation using the buttons below.</p>
</div>
{% endif %}

<div class="workflow-status">
  <strong>Status:</strong> {{ workflow_phase }}
  {% for phase in workflow_completed %}
    <span class="badge">✓ {{ phase }}</span>
  {% endfor %}
</div>
```

Add corresponding CSS to `src/game_survey_workbench/static/app.css`:

```css
.alert-error {
    background: #fef2f2;
    border: 1px solid #fca5a5;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 16px;
    color: #991b1b;
}

.workflow-status {
    padding: 8px 0;
    margin-bottom: 16px;
    color: #6b7280;
}

.badge {
    display: inline-block;
    background: #d1fae5;
    color: #065f46;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.85em;
    margin-left: 4px;
}
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_stage6b_error_feedback.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `python -m pytest --tb=short -q`
Expected: All passing

**Step 6: Commit**

```bash
git add src/game_survey_workbench/templates/analysis/detail.html \
        src/game_survey_workbench/static/app.css \
        tests/test_stage6b_error_feedback.py
git commit -m "feat(stage6b): display workflow errors and phase status in analysis dashboard"
```

---

### Task 4: Questionnaire Version History and Comparison

**Why now:** Iteration is the highest-value missing capability. The data model already supports multiple `QuestionnaireSpecVersion` rows per project — this task exposes them.

**Files:**
- Create: `src/game_survey_workbench/services/questionnaire_versions.py`
- Modify: `src/game_survey_workbench/routes/questionnaires.py`
- Create: `src/game_survey_workbench/templates/questionnaires/history.html`
- Test: `tests/test_stage6c_questionnaire_versions.py`

**Step 1: Write the failing test**

```python
# tests/test_stage6c_questionnaire_versions.py
"""Questionnaire version history and comparison."""
import pytest
from game_survey_workbench.services.questionnaire_versions import (
    list_versions,
    diff_versions,
)


def test_list_versions_returns_all(db_session):
    from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion
    from datetime import datetime, timezone

    for i in range(3):
        v = QuestionnaireSpecVersion(
            project_slug="proj-a",
            version_id=f"v{i}",
            research_goal=f"goal {i}",
            markdown_spec=f"# Draft {i}\n\nContent version {i}",
            citations=[],
            retrieved_snippets=[],
            created_at=datetime(2026, 3, 15, i, 0, 0, tzinfo=timezone.utc),
        )
        db_session.add(v)
    db_session.commit()

    versions = list_versions(db_session, "proj-a")
    assert len(versions) == 3
    # Most recent first
    assert versions[0].version_id == "v2"


def test_diff_versions_shows_changes(db_session):
    from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion
    from datetime import datetime, timezone

    v1 = QuestionnaireSpecVersion(
        project_slug="proj-b",
        version_id="v1",
        research_goal="initial goal",
        markdown_spec="# Survey\n\n1. How often do you play?\n2. What genres?",
        citations=[],
        retrieved_snippets=[],
    )
    v2 = QuestionnaireSpecVersion(
        project_slug="proj-b",
        version_id="v2",
        research_goal="refined goal",
        markdown_spec="# Survey\n\n1. How often do you play?\n2. What genres?\n3. How much do you spend?",
        citations=[],
        retrieved_snippets=[],
    )
    db_session.add_all([v1, v2])
    db_session.commit()

    diff = diff_versions(db_session, "proj-b", "v1", "v2")
    assert diff.added_lines > 0
    assert "How much do you spend" in diff.unified_diff
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stage6c_questionnaire_versions.py -v`
Expected: FAIL — module not found

**Step 3: Implement version service**

```python
# src/game_survey_workbench/services/questionnaire_versions.py
"""Questionnaire version history and diff utilities."""
from __future__ import annotations

import difflib
from dataclasses import dataclass

from sqlmodel import Session, select

from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion


def list_versions(
    session: Session, project_slug: str
) -> list[QuestionnaireSpecVersion]:
    """Return all questionnaire versions for a project, most recent first."""
    stmt = (
        select(QuestionnaireSpecVersion)
        .where(QuestionnaireSpecVersion.project_slug == project_slug)
        .order_by(QuestionnaireSpecVersion.created_at.desc())
    )
    return list(session.exec(stmt).all())


@dataclass
class VersionDiff:
    version_a: str
    version_b: str
    added_lines: int
    removed_lines: int
    unified_diff: str


def diff_versions(
    session: Session,
    project_slug: str,
    version_id_a: str,
    version_id_b: str,
) -> VersionDiff:
    """Compute a unified diff between two questionnaire versions."""
    va = session.exec(
        select(QuestionnaireSpecVersion).where(
            QuestionnaireSpecVersion.project_slug == project_slug,
            QuestionnaireSpecVersion.version_id == version_id_a,
        )
    ).first()
    vb = session.exec(
        select(QuestionnaireSpecVersion).where(
            QuestionnaireSpecVersion.project_slug == project_slug,
            QuestionnaireSpecVersion.version_id == version_id_b,
        )
    ).first()

    if va is None or vb is None:
        raise ValueError(f"Version not found: {version_id_a} or {version_id_b}")

    lines_a = va.markdown_spec.splitlines(keepends=True)
    lines_b = vb.markdown_spec.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            lines_a, lines_b, fromfile=version_id_a, tofile=version_id_b
        )
    )
    unified = "".join(diff_lines)
    added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
    removed = sum(
        1 for l in diff_lines if l.startswith("-") and not l.startswith("---")
    )

    return VersionDiff(
        version_a=version_id_a,
        version_b=version_id_b,
        added_lines=added,
        removed_lines=removed,
        unified_diff=unified,
    )
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_stage6c_questionnaire_versions.py -v`
Expected: PASS (may need a `db_session` fixture — see Step 4a)

**Step 4a: Ensure db_session fixture exists**

If the test needs a `db_session` fixture, check `tests/conftest.py`. If not present, the test should create its own:

```python
@pytest.fixture
def db_session(tmp_path):
    from sqlmodel import Session, create_engine, SQLModel
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
```

**Step 5: Add version history route**

In `src/game_survey_workbench/routes/questionnaires.py`:

```python
@router.get("/projects/{project_slug}/questionnaires/history")
def questionnaire_history(project_slug: str, request: Request):
    versions = list_versions(session, project_slug)
    return templates.TemplateResponse(
        "questionnaires/history.html",
        {"request": request, "project_slug": project_slug, "versions": versions},
    )

@router.get("/projects/{project_slug}/questionnaires/diff")
def questionnaire_diff(
    project_slug: str, va: str, vb: str, request: Request
):
    diff = diff_versions(session, project_slug, va, vb)
    return templates.TemplateResponse(
        "questionnaires/history.html",
        {"request": request, "project_slug": project_slug, "diff": diff},
    )
```

**Step 6: Create history template**

```html
<!-- src/game_survey_workbench/templates/questionnaires/history.html -->
{% extends "layout.html" %}
{% block content %}
<h1>Questionnaire History — {{ project_slug }}</h1>

{% if versions %}
<table>
  <thead>
    <tr><th>Version</th><th>Research Goal</th><th>Created</th><th>Compare</th></tr>
  </thead>
  <tbody>
    {% for v in versions %}
    <tr>
      <td>{{ v.version_id }}</td>
      <td>{{ v.research_goal }}</td>
      <td>{{ v.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
      <td>
        {% if not loop.last %}
        <a href="?va={{ versions[loop.index].version_id }}&vb={{ v.version_id }}">
          vs previous
        </a>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}

{% if diff %}
<h2>Diff: {{ diff.version_a }} → {{ diff.version_b }}</h2>
<p>+{{ diff.added_lines }} lines / -{{ diff.removed_lines }} lines</p>
<pre class="diff">{{ diff.unified_diff }}</pre>
{% endif %}
{% endblock %}
```

**Step 7: Write route-level test**

```python
# Add to tests/test_stage6c_questionnaire_versions.py

def test_history_page_lists_versions(client, tmp_path):
    client.post("/projects", json={"slug": "hist-proj", "name": "History"})
    # Generate two drafts (with fake LLM)
    client.post(
        "/projects/hist-proj/questionnaires/draft",
        json={"research_goal": "first draft"},
    )
    client.post(
        "/projects/hist-proj/questionnaires/draft",
        json={"research_goal": "second draft"},
    )
    resp = client.get("/projects/hist-proj/questionnaires/history")
    assert resp.status_code == 200
    assert b"first draft" in resp.content or b"second draft" in resp.content
```

**Step 8: Run all tests**

Run: `python -m pytest --tb=short -q`
Expected: All passing

**Step 9: Commit**

```bash
git add src/game_survey_workbench/services/questionnaire_versions.py \
        src/game_survey_workbench/routes/questionnaires.py \
        src/game_survey_workbench/templates/questionnaires/history.html \
        tests/test_stage6c_questionnaire_versions.py
git commit -m "feat(stage6c): add questionnaire version history and diff comparison"
```

---

### Task 5: Questionnaire Iterative Refinement with Feedback

**Why now:** With version history visible, the researcher needs a way to say "keep questions 1-3, improve question 4, add a question about spending" and get a refined draft — not a completely new one.

**Files:**
- Modify: `src/game_survey_workbench/services/questionnaires.py`
- Create: `src/game_survey_workbench/prompts/questionnaire_refine.txt`
- Modify: `src/game_survey_workbench/routes/questionnaires.py`
- Test: `tests/test_stage6c_questionnaire_refine.py`

**Step 1: Write the failing test**

```python
# tests/test_stage6c_questionnaire_refine.py
"""Questionnaire iterative refinement with user feedback."""
import pytest
from game_survey_workbench.services.questionnaires import refine_questionnaire_draft


def test_refine_includes_previous_draft_in_context():
    """The refinement prompt should contain the previous draft and the feedback."""
    from unittest.mock import MagicMock

    mock_llm = MagicMock()
    mock_llm.generate.return_value = "# Refined Survey\n\n1. Updated question"

    previous_markdown = "# Original Survey\n\n1. How often do you play?"
    feedback = "Add a question about spending habits"

    result = refine_questionnaire_draft(
        llm_client=mock_llm,
        previous_markdown=previous_markdown,
        feedback=feedback,
        research_goal="understand player behavior",
        knowledge_snippets=[],
    )

    # The LLM should have been called with a prompt containing both
    call_args = mock_llm.generate.call_args[0][0]
    assert "How often do you play" in call_args
    assert "spending habits" in call_args
    assert result.markdown_spec is not None


def test_refine_preserves_version_lineage():
    """Refined draft should reference the parent version."""
    from unittest.mock import MagicMock

    mock_llm = MagicMock()
    mock_llm.generate.return_value = "# Refined\n\n1. Q1"

    result = refine_questionnaire_draft(
        llm_client=mock_llm,
        previous_markdown="# Old\n\n1. Q1",
        feedback="improve clarity",
        research_goal="goal",
        knowledge_snippets=[],
        parent_version_id="v-001",
    )
    assert result.research_goal == "goal [refined: improve clarity]"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stage6c_questionnaire_refine.py -v`
Expected: FAIL — `refine_questionnaire_draft` does not exist

**Step 3: Implement refinement function**

```python
# Add to src/game_survey_workbench/services/questionnaires.py

def refine_questionnaire_draft(
    *,
    llm_client,
    previous_markdown: str,
    feedback: str,
    research_goal: str,
    knowledge_snippets: list[dict],
    parent_version_id: str | None = None,
) -> QuestionnaireSpecVersion:
    """Generate a refined questionnaire draft based on user feedback."""
    prompt = _build_refinement_prompt(
        previous_markdown=previous_markdown,
        feedback=feedback,
        research_goal=research_goal,
        knowledge_snippets=knowledge_snippets,
    )
    response = llm_client.generate(prompt)

    refined_goal = research_goal
    if feedback:
        refined_goal = f"{research_goal} [refined: {feedback}]"

    import uuid

    return QuestionnaireSpecVersion(
        project_slug="",  # caller sets this
        version_id=str(uuid.uuid4())[:8],
        research_goal=refined_goal,
        markdown_spec=response,
        citations=[],
        retrieved_snippets=knowledge_snippets,
    )


def _build_refinement_prompt(
    *,
    previous_markdown: str,
    feedback: str,
    research_goal: str,
    knowledge_snippets: list[dict],
) -> str:
    """Build the LLM prompt for questionnaire refinement."""
    snippets_text = ""
    if knowledge_snippets:
        snippets_text = "\n\n## Knowledge Context\n" + "\n".join(
            s.get("text", "") for s in knowledge_snippets
        )

    return f"""You are a survey research expert. A researcher has drafted a questionnaire and wants to refine it.

## Research Goal
{research_goal}

## Current Draft
{previous_markdown}

## Researcher Feedback
{feedback}

## Instructions
- Keep questions the researcher is satisfied with
- Modify or replace questions based on the feedback
- Add new questions if the feedback requests them
- Maintain professional survey design standards
- Output the complete refined questionnaire in Markdown
{snippets_text}

## Output
Return ONLY the refined questionnaire in Markdown format."""
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_stage6c_questionnaire_refine.py -v`
Expected: PASS

**Step 5: Add refinement form route**

In `src/game_survey_workbench/routes/questionnaires.py`:

```python
@router.post("/projects/{project_slug}/questionnaires/refine-form")
def refine_questionnaire_form(
    project_slug: str,
    feedback: str = Form(...),
    version_id: str = Form(...),
):
    # Load the specified version
    # Call refine_questionnaire_draft with previous markdown + feedback
    # Save as new version
    # Redirect to latest
    ...
```

**Step 6: Add refinement form to questionnaire detail template**

In `src/game_survey_workbench/templates/questionnaires/detail.html`, add below the current spec display:

```html
<h3>Refine This Draft</h3>
<form method="post" action="/projects/{{ project_slug }}/questionnaires/refine-form">
  <input type="hidden" name="version_id" value="{{ spec.version_id }}">
  <label for="feedback">What would you like to change?</label>
  <textarea name="feedback" id="feedback" rows="3"
            placeholder="e.g., Add a question about spending habits, simplify question 3..."></textarea>
  <button type="submit">Refine Draft</button>
</form>
```

**Step 7: Run all tests**

Run: `python -m pytest --tb=short -q`
Expected: All passing

**Step 8: Commit**

```bash
git add src/game_survey_workbench/services/questionnaires.py \
        src/game_survey_workbench/routes/questionnaires.py \
        src/game_survey_workbench/templates/questionnaires/detail.html \
        tests/test_stage6c_questionnaire_refine.py
git commit -m "feat(stage6c): add questionnaire iterative refinement with user feedback"
```

---

### Task 6: Insight Re-generation with Adjusted Parameters

**Why now:** Same iterative principle as questionnaire refinement. A researcher should be able to say "focus more on retention metrics" or "ignore the demographic breakdown" and regenerate insights.

**Files:**
- Modify: `src/game_survey_workbench/routes/insights.py`
- Modify: `src/game_survey_workbench/templates/analysis/detail.html`
- Test: `tests/test_stage6d_insight_iteration.py`

**Step 1: Write the failing test**

```python
# tests/test_stage6d_insight_iteration.py
"""Insight re-generation with adjusted parameters."""
import pytest
from fastapi.testclient import TestClient
from game_survey_workbench.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(workspace_root=tmp_path)
    return TestClient(app, follow_redirects=False)


def test_regenerate_insights_with_different_goal(client, tmp_path):
    """Researcher can re-generate insights with a different research focus."""
    # Setup: project + dataset + initial insights
    client.post("/projects", json={"slug": "iter-proj", "name": "Iter"})
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("Q1,Q2\nsingle_choice,free_text\nA,great game\nB,too expensive\n")
    with open(csv_path, "rb") as f:
        resp = client.post(
            "/projects/iter-proj/datasets/import",
            files={"file": ("data.csv", f, "text/csv")},
        )
    run_id = resp.json().get("analysis_run_id")

    # First insight generation
    resp1 = client.post(
        f"/projects/iter-proj/analysis/{run_id}/insights-generate",
        data={"research_goal": "overall satisfaction"},
        follow_redirects=False,
    )
    assert resp1.status_code in (302, 303)

    # Second generation with different focus
    resp2 = client.post(
        f"/projects/iter-proj/analysis/{run_id}/insights-generate",
        data={"research_goal": "monetization feedback"},
        follow_redirects=False,
    )
    assert resp2.status_code in (302, 303)

    # Both insights should be accessible (not overwritten)
    from sqlmodel import Session, select
    from game_survey_workbench.models.insight import InsightRecord
    from game_survey_workbench.db import get_engine

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        insights = session.exec(
            select(InsightRecord).where(
                InsightRecord.analysis_run_id == run_id
            )
        ).all()
        assert len(insights) >= 1  # at least latest is saved
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stage6d_insight_iteration.py -v`
Expected: FAIL or partial — depending on whether current route overwrites or appends

**Step 3: Modify insight route to support re-generation**

The key change: instead of silently overwriting, the route should create a new `InsightRecord` row (or update the existing one based on the `research_goal`). The analysis dashboard should show the latest insight but link to previous ones.

**Step 4: Run tests and commit**

Run: `python -m pytest --tb=short -q`
Expected: All passing

```bash
git add src/game_survey_workbench/routes/insights.py \
        src/game_survey_workbench/templates/analysis/detail.html \
        tests/test_stage6d_insight_iteration.py
git commit -m "feat(stage6d): support insight re-generation with adjusted research goals"
```

---

### Task 7: Retrieval Relevance Improvement (TF-IDF Weighting)

**Why now:** The current `LocalVectorStore.query()` uses raw term frequency — a document mentioning "game" 10 times scores the same whether the corpus has 2 or 200 documents about games. TF-IDF weighting is a zero-dependency improvement that makes retrieval noticeably better.

**Files:**
- Modify: `src/game_survey_workbench/retrieval/store.py`
- Test: `tests/test_stage6e_retrieval_tfidf.py`

**Step 1: Write the failing test**

```python
# tests/test_stage6e_retrieval_tfidf.py
"""TF-IDF weighted retrieval should rank domain-specific terms higher."""
import pytest
from game_survey_workbench.retrieval.store import LocalVectorStore, StoredChunk


@pytest.fixture
def store_with_corpus(tmp_path):
    store = LocalVectorStore(tmp_path / "artifacts" / "vector_store")
    chunks = [
        StoredChunk(
            chunk_id="c1",
            source_path="doc1.md",
            text="Game monetization through in-app purchases drives revenue",
            doc_type="experience",
            stages=["monetization"],
            tags=["iap"],
            scenario=None,
            priority=0,
        ),
        StoredChunk(
            chunk_id="c2",
            source_path="doc2.md",
            text="The game industry has many games with game-like mechanics",
            doc_type="experience",
            stages=["general"],
            tags=["overview"],
            scenario=None,
            priority=0,
        ),
        StoredChunk(
            chunk_id="c3",
            source_path="doc3.md",
            text="In-app purchase optimization requires understanding player segments",
            doc_type="experience",
            stages=["monetization"],
            tags=["iap", "segments"],
            scenario=None,
            priority=0,
        ),
    ]
    store.save_chunks(chunks)
    return store


def test_iap_query_ranks_specific_over_generic(store_with_corpus):
    """Searching for 'in-app purchase' should rank c1/c3 above c2."""
    results = store_with_corpus.query("in-app purchase monetization", top_k=3)
    result_ids = [r.chunk_id for r in results]
    # c2 mentions "game" 3 times but nothing about IAP
    # c1 and c3 should rank higher due to IDF weighting of "purchase"
    assert result_ids[0] in ("c1", "c3")


def test_generic_term_gets_lower_weight(store_with_corpus):
    """The word 'game' appears in all docs — it should have low IDF weight."""
    results = store_with_corpus.query("game", top_k=3)
    # All docs match, but ranking should not over-favor c2 just because
    # it repeats "game" multiple times
    # With TF-IDF, "game" has low IDF so raw TF advantage is dampened
    assert len(results) == 3
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stage6e_retrieval_tfidf.py -v`
Expected: FAIL — current scoring gives c2 an unfair advantage for "game" queries

**Step 3: Add TF-IDF scoring to LocalVectorStore**

```python
# Modify the query() method in src/game_survey_workbench/retrieval/store.py

import math

def _compute_idf(self, term: str, chunks: list[StoredChunk]) -> float:
    """Inverse document frequency: log(N / (1 + df))."""
    doc_count = sum(1 for c in chunks if term.lower() in c.text.lower())
    return math.log(len(chunks) / (1 + doc_count))

def _tfidf_score(self, query_terms: list[str], chunk: StoredChunk, all_chunks: list[StoredChunk]) -> float:
    """TF-IDF score for a chunk given query terms."""
    text_lower = chunk.text.lower()
    words = text_lower.split()
    total_words = max(len(words), 1)
    score = 0.0
    for term in query_terms:
        tf = words.count(term.lower()) / total_words
        idf = self._compute_idf(term, all_chunks)
        score += tf * idf
    return score
```

Replace the existing raw frequency scoring in `query()` with `_tfidf_score()`.

**Step 4: Run tests**

Run: `python -m pytest tests/test_stage6e_retrieval_tfidf.py -v`
Expected: PASS

**Step 5: Run full test suite (retrieval changes could affect existing tests)**

Run: `python -m pytest --tb=short -q`
Expected: All passing

**Step 6: Commit**

```bash
git add src/game_survey_workbench/retrieval/store.py \
        tests/test_stage6e_retrieval_tfidf.py
git commit -m "feat(stage6e): upgrade retrieval scoring from raw TF to TF-IDF weighting"
```

---

### Task 8: Workflow Progress Display in Analysis Dashboard

**Why now:** With state machine, error feedback, and iteration in place, the analysis dashboard needs a clear visual indicator of what's been done and what's next.

**Files:**
- Modify: `src/game_survey_workbench/templates/analysis/detail.html`
- Modify: `src/game_survey_workbench/static/app.css`
- Test: `tests/test_stage6f_workflow_display.py`

**Step 1: Write the failing test**

```python
# tests/test_stage6f_workflow_display.py
"""Analysis dashboard shows workflow progress."""
import pytest
from fastapi.testclient import TestClient
from game_survey_workbench.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(workspace_root=tmp_path)
    return TestClient(app)


def test_analysis_page_shows_step_checklist(client, tmp_path):
    """The analysis page should display a step-by-step progress checklist."""
    client.post("/projects", json={"slug": "prog-proj", "name": "Progress"})
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("Q1\nsingle_choice\nA\nB\n")
    with open(csv_path, "rb") as f:
        resp = client.post(
            "/projects/prog-proj/datasets/import",
            files={"file": ("data.csv", f, "text/csv")},
        )
    run_id = resp.json().get("analysis_run_id")

    resp = client.get(f"/projects/prog-proj/analysis/{run_id}")
    assert resp.status_code == 200
    # Should show the phase steps
    content = resp.text
    assert "imported" in content.lower() or "dataset imported" in content.lower()
```

**Step 2: Implement progress checklist in template**

Add to `analysis/detail.html`:

```html
<div class="workflow-steps">
  <h3>Research Progress</h3>
  <ol>
    <li class="{{ 'done' if workflow_phase != 'imported' else 'current' }}">
      Dataset Imported ✓
    </li>
    <li class="{{ 'done' if 'coding_complete' in workflow_completed else 'pending' if workflow_phase == 'imported' else 'current' }}">
      Text Coding
    </li>
    <li class="{{ 'done' if 'insights_complete' in workflow_completed else 'pending' }}">
      Insight Synthesis
    </li>
    <li class="{{ 'done' if 'report_complete' in workflow_completed else 'pending' }}">
      Report Generated
    </li>
  </ol>
</div>
```

**Step 3: Run tests and commit**

Run: `python -m pytest --tb=short -q`
Expected: All passing

```bash
git add src/game_survey_workbench/templates/analysis/detail.html \
        src/game_survey_workbench/static/app.css \
        tests/test_stage6f_workflow_display.py
git commit -m "feat(stage6f): add workflow progress checklist to analysis dashboard"
```

---

### Task 9: North-Star Update and Regression Verification

**Files:**
- Modify: `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`
- Run: full test suite

**Step 1: Update north-star with Stage 5 and Stage 6 status**

Add Stage 5 completion status and Stage 6 sub-stage tracking to the north-star document.

**Step 2: Run full test suite**

Run: `python -m pytest --tb=short -q`
Expected: All passing, count should be ~170+ (baseline 160 + new Stage 6 tests)

**Step 3: Commit**

```bash
git add docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md
git commit -m "docs: update north-star with Stage 5 completion and Stage 6 status tracking"
```

---

## Dependency Graph

```
Task 1 (workflow state machine)
  └─→ Task 2 (wire into routes)
        └─→ Task 3 (error feedback UI)
              └─→ Task 8 (progress display)
Task 4 (version history) ──→ Task 5 (iterative refinement)
Task 6 (insight re-generation) — independent, can parallel with Task 4-5
Task 7 (TF-IDF retrieval) — fully independent, can parallel with anything
Task 9 (north-star update) — after all other tasks
```

**Parallelizable groups:**
- Group A: Tasks 1→2→3→8 (workflow state pipeline)
- Group B: Tasks 4→5 (questionnaire iteration)
- Group C: Task 6 (insight iteration)
- Group D: Task 7 (retrieval improvement)

Groups B, C, D are independent of each other and can be worked in any order after Group A establishes the workflow state foundation. However, Task 7 is fully independent and can be done at any time.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `workflow_state` JSON column migration breaks existing rows | Medium | High | Default `{}` maps to initial state via `get_workflow_state()` — no migration needed |
| TF-IDF change breaks existing retrieval tests | Medium | Medium | Run full suite after Task 7; scoring change is monotonic (better ranking, same recall) |
| Questionnaire refinement prompt quality is poor | Medium | Low | Same FakeLLM in tests; real quality is a prompt-tuning concern, not a structural one |
| Silent `pass` removal in routes surfaces unexpected errors | Low | Medium | New error handling records to workflow state instead of crashing |

## Verification Checklist

After all tasks:

- [ ] `python -m pytest --tb=short -q` — all tests pass, count ≥ 170
- [ ] Analysis dashboard shows workflow phase and error messages
- [ ] Questionnaire history page lists all versions with diff links
- [ ] Questionnaire refinement form generates new version based on feedback
- [ ] Insight regeneration with different research goal creates new record
- [ ] Retrieval returns more relevant results for domain-specific queries
- [ ] North-star document reflects Stage 6 completion status
