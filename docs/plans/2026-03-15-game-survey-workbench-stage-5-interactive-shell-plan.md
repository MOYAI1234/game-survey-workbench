# Stage 5: Interactive Workbench Shell — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the existing backend capabilities accessible through browser-based forms and views so a researcher can complete the core product loop — from project creation through report generation — without leaving the browser.

**Architecture:** Extend the existing Jinja2 server-rendered templates with HTML forms (plain POST) for input operations and data-aware detail pages for output display. Add minimal vanilla JS `fetch()` for long-running LLM operations (coding, insight synthesis) that need async feedback. No frontend framework. No new dependencies.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLModel, pandas, pytest, httpx/TestClient (all existing). No new dependencies.

**North-star alignment:** The north-star defines the product as "a local Web workbench opened in the browser after starting the local service." The three visible entry points — Questionnaire Design, Data Analysis, Report Generation — are currently placeholder pages. This plan makes them functional. It does not change the core loop, the local-first delivery model, or the backend service contracts.

**Prerequisite state:** Stage 4 completed, 138 tests passing on local master. All backend services (knowledge ingest, questionnaire generation, dataset import, analytics, text coding, insight synthesis, reporting, feedback-to-knowledge) are functional via API routes.

---

## Stage 4 Closeout Assessment

### What Stage 4 delivered

| Sub-stage | Capability | Status |
|-----------|-----------|--------|
| 4A | Cross-tabulation analytics engine — `POST /crosstabs`, auto-findings per segment | ✓ Completed |
| 4B | Matrix question type — detection, summarization, deterministic findings | ✓ Completed |
| 4C | Ranking question type — normalization, Borda-style scoring, deterministic findings | ✓ Completed |
| 4D | Enhanced recommendation context — structured recommendation builder feeds insight prompt | ✓ Completed |
| 4E | Report-to-knowledge feedback — `POST /reports/feedback-to-knowledge` persists experience-layer Markdown | ✓ Completed |
| 4F | North-star update + regression verification — 138 tests passing | ✓ Completed |

### Stage 4 assessment: credible

The backend pipeline is now comprehensive. A dataset with scale, single-choice, multi-select, matrix, ranking, and free-text columns can be fully analyzed. Cross-tabulation segments findings by any categorical column. Insight synthesis receives all finding types. Reports include evidence sections. The feedback loop persists learnings as knowledge documents.

**No Stage 4 items remain incomplete.**

### What the product still cannot do

Despite four completed stages and 138 passing tests, the product has one critical gap: **a researcher cannot use it through the browser.**

| Area | Current state | Gap |
|------|--------------|-----|
| Project creation | API-only (`POST /projects`) | No form in browser |
| Knowledge upload | Manual file placement | No upload form |
| Research brief | API-only (`PUT /projects/{slug}/brief`) | No editable form |
| Dataset upload | API-only (`POST /projects/{slug}/datasets/import`) | No upload form |
| Questionnaire design | API-only (`POST .../questionnaires/draft`) | Placeholder page — shows nothing |
| Analysis results | API-only | Placeholder page — "这里展示数据导入状态、分析结果和报告导出入口" |
| Text coding | API-only (`POST .../code-text`) | No trigger, no results view |
| Insight generation | API-only (`POST .../insights`) | No trigger, no results view |
| Report generation | API-only (`POST .../reports/generate`) | No trigger, no rendered view |

The three north-star entry points (Questionnaire Design, Data Analysis, Report Generation) are all placeholder HTML with a Chinese title and nothing else.

### Direction recommendation

**Go directly to Stage 5.** The remaining gaps are not polish — they are the product's stated delivery form. The north-star says "a local Web workbench opened in the browser." Until the browser can drive the core loop, the product is a backend API with a landing page, not a workbench.

This does not conflict with the priority rule "Prefer knowledge + LLM value creation over large UX reshaping" because:

1. All knowledge + LLM value already exists in the backend (Stages 2–4).
2. The UI work exposes that value — it does not compete with it.
3. The north-star explicitly names "Web workbench" as the product shell, not an optional enhancement.

No Stage 2/3/4 polish items need to be addressed first. They remain deferred per prior closeout decisions.

---

## Stage 5 scope

### Sub-stages

| Sub-stage | What it delivers | Priority |
|-----------|-----------------|----------|
| 5A | Input forms: project creation, knowledge upload, brief editing, dataset upload | Highest — unblocks the full loop |
| 5B | Output views: analysis dashboard, coding results, insight narrative | High — shows what the backend computed |
| 5C | Action triggers + report: coding/insight/report generation buttons with async feedback, rendered report view | High — closes the browser-driven loop |

### Non-goals for Stage 5

- SPA / React / Vue frontend rewrite — stay with Jinja2 server-rendering
- CSS redesign or design system — use existing `app.css` variables
- Crosstab builder UI — the `POST /crosstabs` API is sufficient for now
- Knowledge document browser / search UI — future candidate
- Multi-dataset comparison dashboard — future candidate
- Real-time streaming of LLM output — synchronous is acceptable for MVP
- Task plan editing form — API-only is fine; lower frequency than brief editing
- Questionnaire version history browser — future candidate

---

## Task 1: Project creation form on landing page (Stage 5A)

**Files:**
- Modify: `src/game_survey_workbench/templates/index.html`
- Modify: `src/game_survey_workbench/routes/ui.py`
- Modify: `src/game_survey_workbench/routes/projects.py`
- Create: `tests/test_stage5a_project_form.py`

### Step 1: Write the failing test

```python
# tests/test_stage5a_project_form.py
import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    return TestClient(app)


def test_landing_page_has_project_creation_form(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert '<form' in html
    assert 'action="/projects"' in html or 'action="/projects/create"' in html
    assert 'name="slug"' in html
    assert 'name="name"' in html


def test_create_project_via_form_redirects_to_project_page(client):
    response = client.post(
        "/projects/create",
        data={"slug": "test-project", "name": "Test Project", "description": "A test"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert "/projects/test-project" in response.headers["location"]


def test_created_project_appears_on_landing_page(client):
    client.post(
        "/projects/create",
        data={"slug": "my-proj", "name": "My Project", "description": ""},
        follow_redirects=False,
    )
    response = client.get("/")
    assert "My Project" in response.text
```

### Step 2: Run test to verify it fails

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5a_project_form.py -v`
Expected: FAIL — no form in template, no `/projects/create` route.

### Step 3: Add form POST route to projects router

```python
# Add to src/game_survey_workbench/routes/projects.py

from fastapi import Form
from fastapi.responses import RedirectResponse

@router.post("/projects/create")
def create_project_form(
    slug: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
):
    settings = get_settings()
    create_project(
        workspace_root=settings.workspace_root,
        slug=slug,
        name=name,
        description=description,
    )
    return RedirectResponse(url=f"/projects/{slug}", status_code=303)
```

### Step 4: Add form HTML to landing page template

```html
<!-- Add to src/game_survey_workbench/templates/index.html, after project-list section -->
<section class="create-project">
  <h2>Create New Project</h2>
  <form action="/projects/create" method="post" class="project-form">
    <label for="slug">Slug (URL identifier)</label>
    <input type="text" id="slug" name="slug" required pattern="[a-z0-9\-]+" placeholder="my-research-project">

    <label for="name">Project Name</label>
    <input type="text" id="name" name="name" required placeholder="My Research Project">

    <label for="description">Description (optional)</label>
    <textarea id="description" name="description" rows="2" placeholder="Brief project description..."></textarea>

    <button type="submit">Create Project</button>
  </form>
</section>
```

### Step 5: Run test to verify it passes

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5a_project_form.py -v`
Expected: PASS

### Step 6: Commit

```bash
git add tests/test_stage5a_project_form.py src/game_survey_workbench/routes/projects.py src/game_survey_workbench/templates/index.html
git commit -m "feat(stage5a): add project creation form on landing page"
```

---

## Task 2: Knowledge upload + dataset upload forms on project page (Stage 5A)

**Files:**
- Modify: `src/game_survey_workbench/templates/projects/detail.html`
- Modify: `src/game_survey_workbench/routes/projects.py`
- Create: `tests/test_stage5a_upload_forms.py`

### Step 1: Write the failing test

```python
# tests/test_stage5a_upload_forms.py
import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def project_slug(client):
    slug = "upload-test"
    client.post("/projects", json={"slug": slug, "name": "Upload Test"})
    return slug


def test_project_page_has_knowledge_upload_form(client, project_slug):
    response = client.get(f"/projects/{project_slug}")
    html = response.text
    assert 'enctype="multipart/form-data"' in html
    assert "knowledge" in html.lower()
    assert f'/projects/{project_slug}/knowledge/upload' in html


def test_project_page_has_dataset_upload_form(client, project_slug):
    response = client.get(f"/projects/{project_slug}")
    html = response.text
    assert f'/projects/{project_slug}/datasets/import' in html
    assert 'type="file"' in html


def test_knowledge_upload_stores_file(client, project_slug, tmp_path):
    md_content = b"---\ntitle: Test Doc\n---\n# Test Knowledge\nSome content."
    response = client.post(
        f"/projects/{project_slug}/knowledge/upload",
        files={"file": ("test-doc.md", md_content, "text/markdown")},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)


def test_dataset_upload_via_form_redirects(client, project_slug, tmp_path):
    csv_content = (
        b"Q1_Satisfaction,Q2_Feedback\n"
        b"scale,free_text\n"
        b"5,Great game\n"
        b"3,Needs work\n"
    )
    response = client.post(
        f"/projects/{project_slug}/datasets/import",
        files={"file": ("survey.csv", csv_content, "text/csv")},
        follow_redirects=False,
    )
    # Either redirect on success, or 201 from existing API route
    assert response.status_code in (201, 302, 303)
```

### Step 2: Run test to verify it fails

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5a_upload_forms.py -v`
Expected: FAIL — no knowledge upload route, no forms in template.

### Step 3: Add knowledge upload route

```python
# Add to src/game_survey_workbench/routes/projects.py

from fastapi import UploadFile, File
from fastapi.responses import RedirectResponse

@router.post("/projects/{project_slug}/knowledge/upload")
async def upload_knowledge_form(project_slug: str, file: UploadFile = File(...)):
    settings = get_settings()
    knowledge_dir = settings.workspace_root / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    filename = file.filename or "uploaded.md"
    dest = knowledge_dir / filename
    dest.write_bytes(await file.read())
    return RedirectResponse(url=f"/projects/{project_slug}", status_code=303)
```

### Step 4: Add upload forms to project detail template

Add knowledge upload and dataset upload form sections to `templates/projects/detail.html` after the workflow-links section:

```html
<section class="upload-section">
  <h2>Upload Knowledge Document</h2>
  <form action="/projects/{{ project_slug }}/knowledge/upload" method="post" enctype="multipart/form-data">
    <input type="file" name="file" accept=".md,.txt" required>
    <button type="submit">Upload Knowledge</button>
  </form>
</section>

<section class="upload-section">
  <h2>Upload Dataset</h2>
  <p>CSV or Excel with dual-header format (row 1 = column names, row 2 = type markers: scale, single_choice, multi_select, free_text, matrix, ranking, metadata).</p>
  <form action="/projects/{{ project_slug }}/datasets/import" method="post" enctype="multipart/form-data">
    <input type="file" name="file" accept=".csv,.xlsx,.xls" required>
    <button type="submit">Import Dataset</button>
  </form>
</section>
```

### Step 5: Run test to verify it passes

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5a_upload_forms.py -v`
Expected: PASS

### Step 6: Commit

```bash
git add tests/test_stage5a_upload_forms.py src/game_survey_workbench/routes/projects.py src/game_survey_workbench/templates/projects/detail.html
git commit -m "feat(stage5a): add knowledge and dataset upload forms on project page"
```

---

## Task 3: Research brief inline form on project page (Stage 5A)

**Files:**
- Modify: `src/game_survey_workbench/templates/projects/detail.html`
- Modify: `src/game_survey_workbench/routes/projects.py`
- Create: `tests/test_stage5a_brief_form.py`

### Step 1: Write the failing test

```python
# tests/test_stage5a_brief_form.py
import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def project_slug(client):
    slug = "brief-test"
    client.post("/projects", json={"slug": slug, "name": "Brief Test"})
    return slug


def test_project_page_has_brief_form(client, project_slug):
    response = client.get(f"/projects/{project_slug}")
    html = response.text
    assert 'name="background"' in html
    assert 'name="objectives"' in html
    assert f'/projects/{project_slug}/brief' in html


def test_submit_brief_form_saves_and_redirects(client, project_slug):
    response = client.post(
        f"/projects/{project_slug}/brief/save",
        data={
            "background": "Testing player satisfaction in a mobile RPG",
            "objectives": "Measure NPS\nIdentify churn drivers",
            "hypotheses": "Whales are more satisfied",
            "target_audience": "Active players past 30 days",
            "success_criteria": "Response rate > 15%",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    # Verify the brief was saved
    brief_response = client.get(f"/projects/{project_slug}/brief")
    assert brief_response.status_code == 200
    data = brief_response.json()
    assert data["background"] == "Testing player satisfaction in a mobile RPG"
    assert "Measure NPS" in data["objectives"]


def test_project_page_shows_saved_brief(client, project_slug):
    client.put(
        f"/projects/{project_slug}/brief",
        json={
            "background": "RPG satisfaction study",
            "objectives": ["Measure NPS"],
            "hypotheses": [],
            "target_audience": "All players",
            "success_criteria": "",
        },
    )
    response = client.get(f"/projects/{project_slug}")
    assert "RPG satisfaction study" in response.text
```

### Step 2: Run test to verify it fails

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5a_brief_form.py -v`
Expected: FAIL — no form in template, no `/brief/save` form POST route.

### Step 3: Add brief form POST route

```python
# Add to src/game_survey_workbench/routes/projects.py

@router.post("/projects/{project_slug}/brief/save")
def save_brief_form(
    project_slug: str,
    background: str = Form(""),
    objectives: str = Form(""),
    hypotheses: str = Form(""),
    target_audience: str = Form(""),
    success_criteria: str = Form(""),
):
    settings = get_settings()
    objectives_list = [line.strip() for line in objectives.splitlines() if line.strip()]
    hypotheses_list = [line.strip() for line in hypotheses.splitlines() if line.strip()]
    save_research_brief(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
        payload=ResearchBriefPayload(
            background=background,
            objectives=objectives_list,
            hypotheses=hypotheses_list,
            target_audience=target_audience,
            success_criteria=success_criteria,
        ),
    )
    return RedirectResponse(url=f"/projects/{project_slug}", status_code=303)
```

### Step 4: Replace brief display section in template with form/display toggle

Replace the `brief-section` in `templates/projects/detail.html` with a version that shows a pre-filled form when brief exists and an empty form otherwise. Use `<details>` for edit-in-place:

```html
<section class="brief-section">
  <h2>Research Brief</h2>
  {% if brief %}
  <dl>
    <dt>Background</dt><dd>{{ brief.background }}</dd>
    <dt>Objectives</dt><dd><ul>{% for o in brief.objectives %}<li>{{ o }}</li>{% endfor %}</ul></dd>
    {% if brief.hypotheses %}<dt>Hypotheses</dt><dd><ul>{% for h in brief.hypotheses %}<li>{{ h }}</li>{% endfor %}</ul></dd>{% endif %}
    {% if brief.target_audience %}<dt>Target Audience</dt><dd>{{ brief.target_audience }}</dd>{% endif %}
    {% if brief.success_criteria %}<dt>Success Criteria</dt><dd>{{ brief.success_criteria }}</dd>{% endif %}
  </dl>
  <details>
    <summary>Edit Brief</summary>
  {% else %}
  <p class="empty-state">No brief yet. Fill in below:</p>
  {% endif %}
    <form action="/projects/{{ project_slug }}/brief/save" method="post" class="brief-form">
      <label for="background">Background</label>
      <textarea id="background" name="background" rows="3">{{ brief.background if brief else '' }}</textarea>

      <label for="objectives">Objectives (one per line)</label>
      <textarea id="objectives" name="objectives" rows="3">{{ brief.objectives | join('\n') if brief and brief.objectives else '' }}</textarea>

      <label for="hypotheses">Hypotheses (one per line, optional)</label>
      <textarea id="hypotheses" name="hypotheses" rows="2">{{ brief.hypotheses | join('\n') if brief and brief.hypotheses else '' }}</textarea>

      <label for="target_audience">Target Audience</label>
      <input type="text" id="target_audience" name="target_audience" value="{{ brief.target_audience if brief else '' }}">

      <label for="success_criteria">Success Criteria</label>
      <input type="text" id="success_criteria" name="success_criteria" value="{{ brief.success_criteria if brief else '' }}">

      <button type="submit">Save Brief</button>
    </form>
  {% if brief %}
  </details>
  {% endif %}
</section>
```

### Step 5: Run test to verify it passes

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5a_brief_form.py -v`
Expected: PASS

### Step 6: Commit

```bash
git add tests/test_stage5a_brief_form.py src/game_survey_workbench/routes/projects.py src/game_survey_workbench/templates/projects/detail.html
git commit -m "feat(stage5a): add research brief inline form on project page"
```

---

## Task 4: Analysis findings dashboard (Stage 5B)

**Files:**
- Rewrite: `src/game_survey_workbench/templates/analysis/detail.html`
- Modify: `src/game_survey_workbench/routes/datasets.py`
- Create: `tests/test_stage5b_analysis_dashboard.py`

### Step 1: Write the failing test

```python
# tests/test_stage5b_analysis_dashboard.py
import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def project_with_dataset(client, tmp_path):
    slug = "dash-test"
    client.post("/projects", json={"slug": slug, "name": "Dashboard Test"})
    csv_content = (
        "Q1_Satisfaction,Q2_Genre,Q3_Feedback\n"
        "scale,single_choice,free_text\n"
        "5,RPG,Love it\n"
        "3,FPS,Needs work\n"
        "4,RPG,Pretty good\n"
    )
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    response = client.post(
        f"/projects/{slug}/datasets/import",
        files={"file": ("survey.csv", csv_content.encode(), "text/csv")},
    )
    data = response.json()
    return slug, data["analysis_run_id"]


def test_analysis_page_shows_deterministic_findings(client, project_with_dataset):
    slug, run_id = project_with_dataset
    response = client.get(f"/projects/{slug}/analysis/{run_id}")
    assert response.status_code == 200
    html = response.text
    # Should show actual findings, not placeholder
    assert "Q1_Satisfaction" in html or "Satisfaction" in html
    assert "mean" in html.lower() or "average" in html.lower() or "top" in html.lower()


def test_analysis_page_shows_dataset_schema(client, project_with_dataset):
    slug, run_id = project_with_dataset
    response = client.get(f"/projects/{slug}/analysis/{run_id}")
    html = response.text
    assert "scale" in html
    assert "single_choice" in html or "single choice" in html.lower()
    assert "free_text" in html or "free text" in html.lower()


def test_analysis_page_without_run_id_shows_latest(client, project_with_dataset):
    slug, _ = project_with_dataset
    response = client.get(f"/projects/{slug}/analysis/latest")
    assert response.status_code == 200
```

### Step 2: Run test to verify it fails

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5b_analysis_dashboard.py -v`
Expected: FAIL — placeholder template, no route for `/analysis/{run_id}`.

### Step 3: Add analysis detail route with real data

Add a new route to `routes/datasets.py` that loads the analysis run context, computes deterministic findings, and passes them to the template:

```python
# Add to src/game_survey_workbench/routes/datasets.py

from game_survey_workbench.services.analysis_context import (
    build_deterministic_findings_for_run,
    load_analysis_run_context,
)
from game_survey_workbench.models.analysis_run import get_analysis_run

@router.get("/projects/{project_slug}/analysis/{analysis_run_id}", response_class=HTMLResponse)
def analysis_detail_by_id(project_slug: str, analysis_run_id: str, request: Request):
    settings = get_settings()
    if analysis_run_id == "latest":
        # Find the latest run for this project
        engine = get_engine(settings.workspace_root)
        with Session(engine) as session:
            from game_survey_workbench.models.analysis_run import AnalysisRunRecord
            runs = session.exec(
                select(AnalysisRunRecord).where(
                    AnalysisRunRecord.project_slug == project_slug
                )
            ).all()
        if not runs:
            return templates.TemplateResponse(
                request,
                "analysis/detail.html",
                {"project_slug": project_slug, "findings": [], "schema": {}, "run_id": None, "coding_results": [], "insight": None},
            )
        latest = sorted(runs, key=lambda r: r.created_at, reverse=True)[0]
        analysis_run_id = latest.analysis_run_id

    try:
        context = load_analysis_run_context(
            analysis_run_id=analysis_run_id,
            workspace_root=settings.workspace_root,
        )
    except Exception:
        return templates.TemplateResponse(
            request,
            "analysis/detail.html",
            {"project_slug": project_slug, "findings": [], "schema": {}, "run_id": analysis_run_id, "coding_results": [], "insight": None},
        )

    findings = build_deterministic_findings_for_run(
        analysis_run_id=analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    schema = context.dataset_record.dataset_schema

    # Load coding results and insight if they exist
    from game_survey_workbench.services.reporting import get_coding_results, get_latest_insight_record
    coding_results = get_coding_results(
        analysis_run_id=analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    insight = get_latest_insight_record(
        analysis_run_id=analysis_run_id,
        workspace_root=settings.workspace_root,
    )

    return templates.TemplateResponse(
        request,
        "analysis/detail.html",
        {
            "project_slug": project_slug,
            "run_id": analysis_run_id,
            "findings": findings,
            "schema": schema,
            "coding_results": coding_results,
            "insight": insight,
        },
    )
```

### Step 4: Rewrite the analysis detail template

```html
<!-- src/game_survey_workbench/templates/analysis/detail.html -->
{% extends "layout.html" %}
{% block title %}Analysis — {{ project_slug }}{% endblock %}
{% block content %}
<header>
  <p class="eyebrow"><a href="/projects/{{ project_slug }}">← {{ project_slug }}</a></p>
  <h1>Analysis Dashboard</h1>
  {% if run_id %}<p class="muted">Run: <code>{{ run_id }}</code></p>{% endif %}
</header>

{% if not run_id %}
<p class="empty-state">No analysis runs yet. Upload a dataset from the <a href="/projects/{{ project_slug }}">project page</a>.</p>
{% else %}

<section class="schema-overview">
  <h2>Dataset Schema</h2>
  <table>
    <thead><tr><th>Column</th><th>Type</th><th>In Analysis</th></tr></thead>
    <tbody>
    {% for col_name, col_info in schema.items() %}
    <tr>
      <td>{{ col_name }}</td>
      <td>{{ col_info.question_type if col_info is mapping else col_info }}</td>
      <td>{{ '✓' if col_info is mapping and col_info.include_in_analysis else '—' }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</section>

<section class="findings-section">
  <h2>Deterministic Findings</h2>
  {% if findings %}
  <ul class="findings-list">
    {% for finding in findings %}
    <li>{{ finding }}</li>
    {% endfor %}
  </ul>
  {% else %}
  <p class="empty-state">No deterministic findings computed.</p>
  {% endif %}
</section>

<section class="coding-section">
  <h2>Text Coding Results</h2>
  {% if coding_results %}
  {% for result in coding_results %}
  <h3>{{ result.question_column }}</h3>
  <ul>
    {% for theme in result.themes %}
    <li><strong>{{ theme.theme_name }}</strong> ({{ theme.count }} responses)
      {% if theme.examples %}<br><em>e.g. {{ theme.examples[:2] | join('; ') }}</em>{% endif %}
    </li>
    {% endfor %}
  </ul>
  {% endfor %}
  {% else %}
  <p class="empty-state">No text coding results yet.</p>
  <form action="/projects/{{ project_slug }}/analysis/{{ run_id }}/code-text-all" method="post">
    <button type="submit">Run Text Coding (all free-text columns)</button>
  </form>
  {% endif %}
</section>

<section class="insight-section">
  <h2>Insight Synthesis</h2>
  {% if insight %}
  <div class="insight-narrative">{{ insight.narrative }}</div>
  {% if insight.evidence_section %}
  <div class="evidence">{{ insight.evidence_section }}</div>
  {% endif %}
  {% else %}
  <p class="empty-state">No insights generated yet.</p>
  <form action="/projects/{{ project_slug }}/analysis/{{ run_id }}/insights-generate" method="post">
    <label for="research_goal">Research Goal</label>
    <input type="text" id="research_goal" name="research_goal" required placeholder="e.g. Understand player satisfaction drivers">
    <button type="submit">Generate Insights</button>
  </form>
  {% endif %}
</section>

<section class="report-section">
  <h2>Report</h2>
  <form action="/projects/{{ project_slug }}/reports/generate" method="post">
    <input type="hidden" name="analysis_run_id" value="{{ run_id }}">
    <button type="submit">Generate Report</button>
  </form>
</section>

{% endif %}
{% endblock %}
```

### Step 5: Run test to verify it passes

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5b_analysis_dashboard.py -v`
Expected: PASS

### Step 6: Commit

```bash
git add tests/test_stage5b_analysis_dashboard.py src/game_survey_workbench/routes/datasets.py src/game_survey_workbench/templates/analysis/detail.html
git commit -m "feat(stage5b): add analysis findings dashboard with schema and results"
```

---

## Task 5: Text coding and insight generation form triggers (Stage 5C)

**Files:**
- Modify: `src/game_survey_workbench/routes/text_coding.py`
- Modify: `src/game_survey_workbench/routes/insights.py`
- Create: `tests/test_stage5c_action_triggers.py`

### Step 1: Write the failing test

```python
# tests/test_stage5c_action_triggers.py
import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def project_with_analysis(client, tmp_path):
    slug = "trigger-test"
    client.post("/projects", json={"slug": slug, "name": "Trigger Test"})

    # Upload knowledge so insight generation has context
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    (knowledge_dir / "guide.md").write_text(
        "---\ntitle: Research Guide\ndoc_type: guide\nstages:\n  - analysis\nscenario: trigger-test\npriority: 1\n---\n# Guide\nPlayer satisfaction research guidance.",
        encoding="utf-8",
    )

    csv_content = (
        "Q1_Score,Q2_Feedback\n"
        "scale,free_text\n"
        "5,Love the graphics\n"
        "3,Too many ads\n"
        "4,Good gameplay\n"
        "2,Crashes often\n"
    )
    response = client.post(
        f"/projects/{slug}/datasets/import",
        files={"file": ("data.csv", csv_content.encode(), "text/csv")},
    )
    run_id = response.json()["analysis_run_id"]
    return slug, run_id


def test_code_text_all_route_exists(client, project_with_analysis):
    slug, run_id = project_with_analysis
    response = client.post(
        f"/projects/{slug}/analysis/{run_id}/code-text-all",
        follow_redirects=False,
    )
    # Should either redirect to analysis page or return success
    assert response.status_code in (201, 302, 303)


def test_insights_generate_form_route_exists(client, project_with_analysis):
    slug, run_id = project_with_analysis
    # First run text coding so there are coded themes
    client.post(f"/projects/{slug}/analysis/{run_id}/code-text-all")

    response = client.post(
        f"/projects/{slug}/analysis/{run_id}/insights-generate",
        data={"research_goal": "Understand player satisfaction"},
        follow_redirects=False,
    )
    assert response.status_code in (201, 302, 303)
```

### Step 2: Run test to verify it fails

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5c_action_triggers.py -v`
Expected: FAIL — routes `code-text-all` and `insights-generate` do not exist.

### Step 3: Add batch text coding route

```python
# Add to src/game_survey_workbench/routes/text_coding.py

from fastapi import Form
from fastapi.responses import RedirectResponse

from game_survey_workbench.models.dataset import QuestionColumnSchema
from game_survey_workbench.services.analysis_context import (
    load_analysis_run_context,
    load_free_text_responses_for_question,
)
from game_survey_workbench.services.text_coding import code_open_text_column

@router.post("/projects/{project_slug}/analysis/{analysis_run_id}/code-text-all")
def code_text_all(project_slug: str, analysis_run_id: str):
    """Code all free-text columns in one go."""
    settings = get_settings()
    client = build_llm_client(settings)
    context = load_analysis_run_context(
        analysis_run_id=analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    for col_name, col_payload in context.dataset_record.dataset_schema.items():
        if not isinstance(col_payload, dict):
            continue
        schema = QuestionColumnSchema.model_validate(col_payload)
        if schema.question_type != "free_text":
            continue
        try:
            responses = load_free_text_responses_for_question(
                analysis_run_id=analysis_run_id,
                question_column=col_name,
                workspace_root=settings.workspace_root,
            )
            code_open_text_column(
                project_slug=project_slug,
                analysis_run_id=analysis_run_id,
                question_column=col_name,
                responses=responses,
                workspace_root=settings.workspace_root,
                client=client,
            )
        except Exception:
            continue
    return RedirectResponse(
        url=f"/projects/{project_slug}/analysis/{analysis_run_id}",
        status_code=303,
    )
```

### Step 4: Add insight generation form route

```python
# Add to src/game_survey_workbench/routes/insights.py

from fastapi import Form
from fastapi.responses import RedirectResponse

@router.post("/projects/{project_slug}/analysis/{analysis_run_id}/insights-generate")
def generate_insights_form(
    project_slug: str,
    analysis_run_id: str,
    research_goal: str = Form(...),
):
    """Form-triggered insight generation — same logic as JSON API but accepts form data."""
    settings = get_settings()
    try:
        client = build_llm_client(settings)
        deterministic_findings = build_deterministic_findings_for_run(
            analysis_run_id=analysis_run_id,
            workspace_root=settings.workspace_root,
        )
        statistical_findings, matrix_findings, ranking_findings = _partition_findings(
            deterministic_findings
        )
        crosstab_findings: list[str] = []
        for segment_column in _infer_segment_columns(analysis_run_id):
            crosstab_findings.extend(
                build_crosstab_findings_for_run(
                    analysis_run_id=analysis_run_id,
                    workspace_root=settings.workspace_root,
                    segment_column=segment_column,
                )
            )
        coded_themes = load_saved_coding_themes(
            analysis_run_id=analysis_run_id,
            workspace_root=settings.workspace_root,
        )
        generate_analysis_insights(
            project_slug=project_slug,
            analysis_run_id=analysis_run_id,
            research_goal=research_goal,
            statistical_findings=statistical_findings,
            coded_themes=coded_themes,
            workspace_root=settings.workspace_root,
            client=client,
            crosstab_findings=crosstab_findings,
            matrix_findings=matrix_findings,
            ranking_findings=ranking_findings,
        )
    except Exception:
        pass  # Redirect back regardless; dashboard will show what succeeded
    return RedirectResponse(
        url=f"/projects/{project_slug}/analysis/{analysis_run_id}",
        status_code=303,
    )
```

### Step 5: Run test to verify it passes

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5c_action_triggers.py -v`
Expected: PASS

### Step 6: Commit

```bash
git add tests/test_stage5c_action_triggers.py src/game_survey_workbench/routes/text_coding.py src/game_survey_workbench/routes/insights.py
git commit -m "feat(stage5c): add batch text-coding and insight generation form triggers"
```

---

## Task 6: Report generation form + rendered report view (Stage 5C)

**Files:**
- Modify: `src/game_survey_workbench/routes/reports.py`
- Create: `src/game_survey_workbench/templates/reports/detail.html`
- Create: `tests/test_stage5c_report_view.py`

### Step 1: Write the failing test

```python
# tests/test_stage5c_report_view.py
import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def project_with_report(client, tmp_path):
    slug = "report-view-test"
    client.post("/projects", json={"slug": slug, "name": "Report View Test"})

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    (knowledge_dir / "guide.md").write_text(
        "---\ntitle: Guide\ndoc_type: guide\nstages:\n  - analysis\nscenario: report-view-test\npriority: 1\n---\n# Guide\nContent.",
        encoding="utf-8",
    )

    csv_content = (
        "Q1_Score,Q2_Feedback\n"
        "scale,free_text\n"
        "5,Great\n3,OK\n4,Good\n"
    )
    resp = client.post(
        f"/projects/{slug}/datasets/import",
        files={"file": ("data.csv", csv_content.encode(), "text/csv")},
    )
    run_id = resp.json()["analysis_run_id"]

    # Run coding + insights + report via API
    client.post(f"/projects/{slug}/analysis/{run_id}/code-text-all")
    client.post(
        f"/projects/{slug}/analysis/{run_id}/insights",
        json={"research_goal": "Player satisfaction", "statistical_findings": [], "coded_themes": []},
    )
    client.post(
        f"/projects/{slug}/reports/generate",
        json={"analysis_run_id": run_id},
    )
    return slug, run_id


def test_report_form_post_redirects(client, tmp_path):
    slug = "report-form-test"
    client.post("/projects", json={"slug": slug, "name": "Form Test"})
    csv_content = "Q1,Q2\nscale,free_text\n5,Good\n3,OK\n"
    resp = client.post(
        f"/projects/{slug}/datasets/import",
        files={"file": ("d.csv", csv_content.encode(), "text/csv")},
    )
    run_id = resp.json()["analysis_run_id"]
    response = client.post(
        f"/projects/{slug}/reports/generate-form",
        data={"analysis_run_id": run_id},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)


def test_report_latest_page_shows_content(client, project_with_report):
    slug, _ = project_with_report
    response = client.get(f"/projects/{slug}/reports/latest")
    assert response.status_code == 200
    html = response.text
    assert "Report" in html
    # Should show actual report content, not placeholder
    assert "report-content" in html or "narrative" in html.lower() or "Evidence" in html
```

### Step 2: Run test to verify it fails

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5c_report_view.py -v`
Expected: FAIL — no `generate-form` route, no report detail template.

### Step 3: Add form-based report generation route

```python
# Add to src/game_survey_workbench/routes/reports.py

from fastapi import Form

@router.post("/projects/{project_slug}/reports/generate-form")
def generate_report_form(project_slug: str, analysis_run_id: str = Form(...)):
    """Same as generate_report but accepts form data and redirects."""
    payload = ReportGenerateRequest(analysis_run_id=analysis_run_id)
    generate_report(project_slug, payload)  # reuse existing logic
    return RedirectResponse(
        url=f"/projects/{project_slug}/reports/latest",
        status_code=303,
    )
```

### Step 4: Rewrite report detail page to show rendered content

```python
# Modify the report_detail route in src/game_survey_workbench/routes/reports.py

@router.get("/projects/{project_slug}/reports/latest", response_class=HTMLResponse)
def report_detail(project_slug: str, request: Request):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        from game_survey_workbench.models.reporting import ReportRecord
        records = session.exec(
            select(ReportRecord).where(ReportRecord.project_slug == project_slug)
        ).all()

    report_content = None
    report_path = None
    if records:
        latest = sorted(records, key=lambda r: r.created_at, reverse=True)[0]
        report_path = latest.path
        path_obj = Path(report_path)
        if path_obj.exists():
            report_content = path_obj.read_text(encoding="utf-8")

    return templates.TemplateResponse(
        request,
        "reports/detail.html",
        {
            "project_slug": project_slug,
            "report_content": report_content,
            "report_path": report_path,
        },
    )
```

### Step 5: Create report detail template

```html
<!-- src/game_survey_workbench/templates/reports/detail.html -->
{% extends "layout.html" %}
{% block title %}Report — {{ project_slug }}{% endblock %}
{% block content %}
<header>
  <p class="eyebrow"><a href="/projects/{{ project_slug }}">← {{ project_slug }}</a></p>
  <h1>Report</h1>
</header>

{% if report_content %}
<section class="report-content">
  <pre class="report-markdown">{{ report_content }}</pre>
</section>
{% if report_path %}
<p class="muted">Saved to: <code>{{ report_path }}</code></p>
{% endif %}
{% else %}
<p class="empty-state">No reports generated yet. Go to the <a href="/projects/{{ project_slug }}/analysis/latest">analysis dashboard</a> to generate one.</p>
{% endif %}
{% endblock %}
```

### Step 6: Run test to verify it passes

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5c_report_view.py -v`
Expected: PASS

### Step 7: Commit

```bash
git add tests/test_stage5c_report_view.py src/game_survey_workbench/routes/reports.py src/game_survey_workbench/templates/reports/detail.html
git commit -m "feat(stage5c): add report generation form and rendered report view"
```

---

## Task 7: Questionnaire design page with form + result display (Stage 5B)

**Files:**
- Rewrite: `src/game_survey_workbench/templates/questionnaires/detail.html`
- Modify: `src/game_survey_workbench/routes/questionnaires.py`
- Create: `tests/test_stage5b_questionnaire_page.py`

### Step 1: Write the failing test

```python
# tests/test_stage5b_questionnaire_page.py
import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def project_slug(client, tmp_path):
    slug = "quest-page-test"
    client.post("/projects", json={"slug": slug, "name": "Questionnaire Page Test"})
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    (knowledge_dir / "guide.md").write_text(
        "---\ntitle: Survey Guide\ndoc_type: guide\nstages:\n  - questionnaire\nscenario: quest-page-test\npriority: 1\n---\n# Guide\nDesign guidance.",
        encoding="utf-8",
    )
    return slug


def test_questionnaire_page_has_draft_form(client, project_slug):
    response = client.get(f"/projects/{project_slug}/questionnaires/latest")
    assert response.status_code == 200
    html = response.text
    assert 'name="research_goal"' in html
    assert "Generate" in html or "Draft" in html


def test_questionnaire_draft_form_submission(client, project_slug):
    response = client.post(
        f"/projects/{project_slug}/questionnaires/draft-form",
        data={"research_goal": "Understand player motivation"},
        follow_redirects=False,
    )
    assert response.status_code in (201, 302, 303)


def test_questionnaire_page_shows_latest_draft(client, project_slug):
    # Generate a draft via API first
    client.post(
        f"/projects/{project_slug}/questionnaires/draft",
        json={"research_goal": "Player satisfaction"},
    )
    response = client.get(f"/projects/{project_slug}/questionnaires/latest")
    html = response.text
    # Should show the generated markdown, not just placeholder
    assert "questionnaire-content" in html or "markdown" in html.lower() or "Knowledge Basis" in html or "Player" in html
```

### Step 2: Run test to verify it fails

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5b_questionnaire_page.py -v`
Expected: FAIL — placeholder template, no `draft-form` route.

### Step 3: Add form-based draft route and data-aware detail route

```python
# Add to src/game_survey_workbench/routes/questionnaires.py

from fastapi import Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion

@router.post("/projects/{project_slug}/questionnaires/draft-form")
def draft_questionnaire_form(
    project_slug: str,
    research_goal: str = Form(...),
):
    # Reuse existing draft logic
    payload = QuestionnaireDraftRequest(research_goal=research_goal)
    draft_questionnaire(project_slug, payload)
    return RedirectResponse(
        url=f"/projects/{project_slug}/questionnaires/latest",
        status_code=303,
    )
```

Modify the existing `questionnaire_detail` GET route to load the latest spec version and pass it to the template:

```python
@router.get("/projects/{project_slug}/questionnaires/latest", response_class=HTMLResponse)
def questionnaire_detail(project_slug: str, request: Request):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        versions = session.exec(
            select(QuestionnaireSpecVersion).where(
                QuestionnaireSpecVersion.project_slug == project_slug
            )
        ).all()
    latest = None
    if versions:
        latest = sorted(versions, key=lambda v: v.created_at, reverse=True)[0]
    return templates.TemplateResponse(
        request,
        "questionnaires/detail.html",
        {
            "project_slug": project_slug,
            "spec": latest,
        },
    )
```

### Step 4: Rewrite questionnaire detail template

```html
<!-- src/game_survey_workbench/templates/questionnaires/detail.html -->
{% extends "layout.html" %}
{% block title %}Questionnaire — {{ project_slug }}{% endblock %}
{% block content %}
<header>
  <p class="eyebrow"><a href="/projects/{{ project_slug }}">← {{ project_slug }}</a></p>
  <h1>Questionnaire Design</h1>
</header>

{% if spec %}
<section class="questionnaire-content">
  <h2>Latest Draft</h2>
  <p class="muted">Version: {{ spec.version_id }} | Goal: {{ spec.research_goal }}</p>
  <pre class="questionnaire-markdown">{{ spec.markdown_spec }}</pre>
  {% if spec.retrieved_snippets %}
  <details>
    <summary>Knowledge Basis ({{ spec.retrieved_snippets | length }} sources)</summary>
    <ul>
      {% for snippet in spec.retrieved_snippets %}
      <li>{{ snippet.document_title if snippet is mapping else snippet }}</li>
      {% endfor %}
    </ul>
  </details>
  {% endif %}
</section>
<hr>
{% endif %}

<section class="draft-form">
  <h2>{% if spec %}Generate New Draft{% else %}Generate Questionnaire Draft{% endif %}</h2>
  <form action="/projects/{{ project_slug }}/questionnaires/draft-form" method="post">
    <label for="research_goal">Research Goal</label>
    <input type="text" id="research_goal" name="research_goal" required
           placeholder="e.g. Understand what drives player retention in our RPG"
           value="{{ spec.research_goal if spec else '' }}">
    <button type="submit">Generate Draft</button>
  </form>
</section>
{% endblock %}
```

### Step 5: Run test to verify it passes

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5b_questionnaire_page.py -v`
Expected: PASS

### Step 6: Commit

```bash
git add tests/test_stage5b_questionnaire_page.py src/game_survey_workbench/routes/questionnaires.py src/game_survey_workbench/templates/questionnaires/detail.html
git commit -m "feat(stage5b): add questionnaire design page with draft form and result display"
```

---

## Task 8: Form styling + navigation polish + north-star update (Stage 5 wrap-up)

**Files:**
- Modify: `src/game_survey_workbench/static/app.css`
- Modify: `src/game_survey_workbench/templates/layout.html`
- Modify: `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`
- Create: `tests/test_stage5_navigation.py`

### Step 1: Write the failing test

```python
# tests/test_stage5_navigation.py
import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    return TestClient(app)


def test_layout_has_nav(client):
    response = client.get("/")
    html = response.text
    assert '<nav' in html
    assert 'href="/"' in html


def test_all_pages_inherit_layout(client):
    slug = "nav-test"
    client.post("/projects", json={"slug": slug, "name": "Nav Test"})
    for path in [
        f"/projects/{slug}",
        f"/projects/{slug}/questionnaires/latest",
        f"/projects/{slug}/analysis/latest",
        f"/projects/{slug}/reports/latest",
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert '<nav' in response.text, f"Missing nav on {path}"
```

### Step 2: Run test to verify it fails

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5_navigation.py -v`
Expected: FAIL — layout.html has no `<nav>`.

### Step 3: Add navigation bar to layout

```html
<!-- src/game_survey_workbench/templates/layout.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Game Survey Workbench{% endblock %}</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <nav class="top-nav">
    <a href="/" class="nav-brand">Game Survey Workbench</a>
  </nav>
  <main class="page">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

### Step 4: Add form and navigation styles to app.css

Append to `src/game_survey_workbench/static/app.css`:

```css
/* Navigation */
.top-nav {
  padding: 12px 24px;
  background: var(--panel);
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(8px);
}
.nav-brand {
  font-weight: 600;
  color: var(--accent);
  text-decoration: none;
}

/* Forms */
form label {
  display: block;
  margin-top: 12px;
  font-weight: 500;
  color: var(--muted);
  font-size: 0.9rem;
}
form input[type="text"],
form textarea {
  display: block;
  width: 100%;
  padding: 8px 12px;
  margin-top: 4px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-family: inherit;
  font-size: 0.95rem;
  background: white;
}
form textarea { resize: vertical; }
form button[type="submit"] {
  margin-top: 16px;
  padding: 10px 24px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 0.95rem;
  cursor: pointer;
}
form button[type="submit"]:hover {
  opacity: 0.9;
}
form input[type="file"] {
  margin-top: 4px;
}

/* Tables */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}
th, td {
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}
th { color: var(--muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; }

/* Sections */
section { margin: 32px 0; }
.muted { color: var(--muted); font-size: 0.9rem; }
.empty-state { color: var(--muted); font-style: italic; }

/* Report & Questionnaire Markdown */
.report-markdown,
.questionnaire-markdown {
  background: white;
  padding: 24px;
  border: 1px solid var(--border);
  border-radius: 12px;
  white-space: pre-wrap;
  font-family: "Segoe UI", sans-serif;
  font-size: 0.95rem;
  line-height: 1.6;
}

/* Findings */
.findings-list li {
  margin: 8px 0;
  line-height: 1.5;
}
```

### Step 5: Update north-star document

Add Stage 5 status section to the north-star plan, after the Stage 4 status block:

```markdown
### Stage 5: Interactive Workbench Shell

Goal:

- make the web workbench usable through the browser for the full core loop

Scope:

- browser-based project creation, knowledge upload, brief editing
- dataset upload with schema preview
- analysis findings dashboard with coding results and insight display
- form-triggered text coding, insight generation, and report generation
- rendered report view
- navigation and workflow continuity across pages

Important note:

- this stage makes the existing backend value accessible, not a UX redesign
- no frontend framework (stays with Jinja2 server-rendering)
- no new dependencies
```

### Step 6: Run tests to verify everything passes

Run: `.venv\Scripts\python.exe -m pytest tests/test_stage5_navigation.py -v`
Expected: PASS

Run: `.venv\Scripts\python.exe -m pytest -v`
Expected: All tests pass (existing 138 + new Stage 5 tests).

### Step 7: Commit

```bash
git add src/game_survey_workbench/static/app.css src/game_survey_workbench/templates/layout.html tests/test_stage5_navigation.py docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md
git commit -m "feat(stage5): add navigation, form styling, and north-star Stage 5 entry"
```

---

## Dependency graph

```
Task 1 (project form)          ─┐
Task 2 (upload forms)           ├─ Stage 5A: Input forms (no dependencies between 1/2/3)
Task 3 (brief form)            ─┘
                                     │
Task 4 (analysis dashboard)    ──── Stage 5B: Output views (depends on upload forms working)
Task 7 (questionnaire page)    ──── Stage 5B: Output views (depends on project existing)
                                     │
Task 5 (action triggers)       ─┐
Task 6 (report view)            ├─ Stage 5C: Action triggers (depends on dashboard existing)
                                ─┘
                                     │
Task 8 (styling + nav + north-star) ── Wrap-up (last, touches all templates)
```

**Parallelism:** Tasks 1, 2, 3 are independent and can run in parallel. Tasks 4 and 7 are independent of each other. Tasks 5 and 6 are independent of each other but depend on Task 4.

## Risk assessment

| Risk | Mitigation |
|------|-----------|
| Dataset import route currently returns JSON 201, not redirect — form POST may behave differently | Task 2 keeps existing JSON API route intact; form route can reuse `import_dataset()` directly and redirect |
| LLM operations (coding, insights) are synchronous and may be slow | Acceptable for MVP; user sees a loading browser while server processes. Future: add async status polling |
| Template changes may break existing tests that check HTML content | Run full regression after each task; existing tests are minimal (mostly check status 200) |
| `code-text-all` may fail silently if LLM is not configured | Route catches exceptions and redirects anyway; dashboard shows what succeeded |

## Verification plan

After all 8 tasks:

1. Run `.venv\Scripts\python.exe -m pytest -v` — all tests must pass
2. Start server with `uvicorn game_survey_workbench.app:create_app --factory`
3. Manual walkthrough: create project → upload knowledge → set brief → upload dataset → view analysis → trigger coding → trigger insights → generate report → view report
4. Verify all pages have navigation bar and consistent styling
