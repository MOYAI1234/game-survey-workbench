# 2.0F Experience Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the visual presentation with Pico CSS, rebrand to "极光问卷", and add loading spinners for all LLM-triggering forms.

**Architecture:** Three-phase approach: (1) Pico CSS integration with brand override layer, (2) product rebrand from "游戏问卷研究工作台" to "极光问卷", (3) pure-frontend JS spinner for LLM forms. No Python route changes. All changes are in templates, static assets, and tests.

**Tech Stack:** Pico CSS v2 (CDN), vanilla JavaScript (~30 lines), CSS @keyframes animation, Jinja2 templates

---

## Phase 1: Pico CSS Integration (Tasks 1-4)

### Task 1: Pico CSS link + layout container

**Files:**
- Modify: `src/game_survey_workbench/templates/layout.html`
- Test: `tests/test_pico_integration.py`

**Step 1: Write the failing test**

Create `tests/test_pico_integration.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    with TestClient(create_app()) as test_client:
        yield test_client


def test_layout_includes_pico_css(client: TestClient):
    response = client.get("/")
    html = response.text
    assert "pico" in html.lower()
    assert "cdn.jsdelivr.net" in html or "pico.min.css" in html


def test_main_has_container_class(client: TestClient):
    response = client.get("/")
    html = response.text
    assert 'class="container' in html


def test_html_has_data_theme(client: TestClient):
    response = client.get("/")
    html = response.text
    assert 'data-theme="light"' in html
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pico_integration.py -v`
Expected: FAIL — no pico reference, no container class, no data-theme in current layout

**Step 3: Implement the layout changes**

Edit `src/game_survey_workbench/templates/layout.html` to become:

```html
<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}极光问卷{% endblock %}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <nav class="top-nav">
    <a href="/" class="nav-brand">极光问卷</a>
    <a href="/knowledge" class="nav-link">共享知识库</a>
  </nav>
  <main class="container page">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

Key changes:
- `<html>` gets `data-theme="light"`
- Pico CDN link added **before** `app.css` (so app.css overrides Pico)
- `<main>` gets `class="container page"` (Pico uses `container` for centered layout)
- Title and nav-brand text will be updated to 极光问卷 (brand change is in Task 5, but we do it here since we're touching the file)

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pico_integration.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pico_integration.py src/game_survey_workbench/templates/layout.html
git commit -m "feat(2.0F): add Pico CSS CDN link and container class to layout"
```

---

### Task 2: Map Pico CSS custom properties to brand colors

**Files:**
- Modify: `src/game_survey_workbench/static/app.css`
- Test: `tests/test_pico_integration.py` (extend)

**Step 1: Write the failing test**

Append to `tests/test_pico_integration.py`:

```python
def test_app_css_defines_pico_primary(client: TestClient):
    response = client.get("/static/app.css")
    css = response.text
    assert "--pico-primary" in css
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pico_integration.py::test_app_css_defines_pico_primary -v`
Expected: FAIL — current app.css has no --pico-primary

**Step 3: Rewrite app.css with Pico overrides**

Replace the full `:root` block and remove rules that Pico now handles. The new `app.css` should be:

```css
/* ── Brand tokens ─────────────────────────────── */
:root {
  color-scheme: light;

  /* Brand palette */
  --bg: #f5f1e8;
  --panel: rgba(255, 255, 255, 0.78);
  --text: #1f1a14;
  --muted: #6a5f52;
  --accent: #b2552d;
  --border: rgba(31, 26, 20, 0.1);

  /* Map brand → Pico custom properties */
  --pico-primary: #b2552d;
  --pico-primary-hover: #9a4526;
  --pico-primary-focus: rgba(178, 85, 45, 0.25);
  --pico-primary-inverse: #fff;
  --pico-border-radius: 12px;
  --pico-font-family: "Segoe UI", "PingFang SC", sans-serif;
  --pico-background-color: var(--bg);
  --pico-color: var(--text);
  --pico-muted-color: var(--muted);
  --pico-card-background-color: var(--panel);
  --pico-card-border-color: var(--border);
}

/* ── Body background (gradient override) ──────── */
body {
  margin: 0;
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(178, 85, 45, 0.18), transparent 32%),
    linear-gradient(135deg, #efe6d6, var(--bg));
}

/* ── Sticky navigation ────────────────────────── */
.top-nav {
  position: sticky;
  top: 0;
  z-index: 10;
  padding: 14px 24px;
  background: rgba(255, 255, 255, 0.82);
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  gap: 24px;
}

.nav-brand {
  color: var(--accent);
  font-weight: 700;
  text-decoration: none;
  letter-spacing: 0.04em;
}

.nav-link {
  color: var(--muted);
  text-decoration: none;
  font-size: 0.92rem;
}

.nav-link:hover {
  color: var(--accent);
}

/* ── Page container refinement ────────────────── */
.page {
  padding-top: 48px;
  padding-bottom: 80px;
}

/* ── Glass card panels ────────────────────────── */
.hero,
section,
header,
details {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 24px;
  backdrop-filter: blur(8px);
  padding: 24px;
  margin-bottom: 24px;
}

/* ── Eyebrow (back link) ─────────────────────── */
.eyebrow {
  margin: 0 0 12px;
  color: var(--accent);
  font-size: 0.85rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

/* ── Status badges ────────────────────────────── */
.status-badge {
  display: inline-block;
  margin-left: 8px;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(178, 85, 45, 0.12);
  color: var(--accent);
  font-size: 0.8rem;
  font-weight: 700;
}

/* ── Workflow alerts ──────────────────────────── */
.workflow-alert {
  border-left: 4px solid #c94c3b;
}

.alert-error {
  background: rgba(201, 76, 59, 0.1);
}

.alert-success {
  background: #f0fdf4;
  border: 1px solid #86efac;
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 16px;
  color: #166534;
}

/* ── Workflow steps ───────────────────────────── */
.workflow-list {
  display: grid;
  gap: 12px;
  padding-left: 20px;
}

.step-item.done {
  color: #2f6b2f;
  font-weight: 700;
}

.step-item.current {
  color: var(--accent);
  font-weight: 700;
}

.step-item.pending {
  color: var(--muted);
}

/* ── Pre-formatted content ────────────────────── */
.report-markdown,
.questionnaire-markdown,
.insight-narrative,
.evidence {
  white-space: pre-wrap;
  line-height: 1.65;
}

.report-markdown,
.questionnaire-markdown {
  margin: 0;
  padding: 0;
  background: transparent;
  border: 0;
}

/* ── Utility classes ──────────────────────────── */
.muted,
.empty-state,
.project-desc,
.project-status {
  color: var(--muted);
}

.help-text {
  font-size: 0.9em;
  color: #6b7280;
  margin-top: 4px;
  margin-bottom: 12px;
}

.step-hint {
  font-size: 0.85em;
  color: #2563eb;
  margin-left: 8px;
}

.badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(178, 85, 45, 0.12);
  color: var(--accent);
  font-size: 0.75rem;
  font-weight: 700;
}

/* ── Responsive ───────────────────────────────── */
@media (max-width: 720px) {
  .page {
    padding-top: 24px;
    padding-bottom: 48px;
  }

  .top-nav {
    padding: 12px 16px;
  }

  section,
  header {
    padding: 18px;
  }
}
```

Key changes vs old app.css:
- **Removed:** `*` box-sizing (Pico handles it), `label` styling (Pico handles form labels), `input/textarea` styling (Pico handles form controls), `button[type="submit"]` styling (Pico uses `--pico-primary`), `table/th/td` styling (Pico handles tables), `a` color rule (Pico uses primary), `code/pre` font (Pico handles it), `ul/ol/dl` margin (Pico handles it), `li + li` margin, `hr` styling
- **Added:** `--pico-*` property mappings, `.nav-link` style, flex layout on `.top-nav`
- **Kept:** Glass card panels, gradient background, nav sticky behavior, workflow step colors, alert styles, `.badge`, responsive overrides

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pico_integration.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/static/app.css
git commit -m "feat(2.0F): slim down app.css with Pico CSS property mappings"
```

---

### Task 3: Fix select element Pico compatibility

**Context:** Pico CSS styles `<select>` elements automatically, but the project settings form in `projects/detail.html` has a bare `<select>` without any wrapping. Pico should handle it well, but we need to verify all forms render correctly with Pico.

**Files:**
- Test: `tests/test_pico_integration.py` (extend)

**Step 1: Write the failing test**

Append to `tests/test_pico_integration.py`:

```python
def test_project_settings_form_renders_with_pico(client: TestClient):
    """Ensure the select element on project detail page renders."""
    client.post("/projects", json={"slug": "pico-test", "name": "Pico Test"})
    response = client.get("/projects/pico-test")
    assert response.status_code == 200
    html = response.text
    assert '<select name="language"' in html
    assert "保存设置" in html


def test_knowledge_page_renders_with_pico(client: TestClient):
    response = client.get("/knowledge")
    assert response.status_code == 200
    html = response.text
    assert '<select id="stage"' in html
    assert "共享知识库" in html


def test_analysis_page_renders_with_pico(client: TestClient):
    client.post("/projects", json={"slug": "ana-pico", "name": "Analysis Pico"})
    response = client.get("/projects/ana-pico/analysis/latest")
    assert response.status_code == 200
```

**Step 2: Run test to verify it passes (or fails)**

Run: `pytest tests/test_pico_integration.py -v`
Expected: These should PASS if the Pico + app.css changes are correct. If any fail, investigate template rendering issues and fix.

**Step 3: Commit**

```bash
git add tests/test_pico_integration.py
git commit -m "test(2.0F): add Pico CSS compatibility tests for all form pages"
```

---

### Task 4: Visual smoke test across all pages

**Context:** After Pico CSS integration, manually verify that all 12 template pages render correctly. This task is a manual checklist — no automated test needed.

**Files:**
- None (manual verification)

**Step 1: Start the dev server**

Run: `cd src && python -m game_survey_workbench` (or however the app starts)

**Step 2: Manual checklist**

Visit each page and verify no visual breakage:

- [ ] `GET /` — Landing page: hero section, project list, create form
- [ ] `GET /knowledge` — Knowledge library: filter form, upload form, document list
- [ ] `GET /projects/{slug}` — Project detail: settings form, brief form, knowledge selection, data upload
- [ ] `GET /projects/{slug}/questionnaires/latest` — Questionnaire: draft form, refine form, download links
- [ ] `GET /projects/{slug}/analysis/latest` — Analysis: workflow steps, schema table, coding section, insight section
- [ ] `GET /projects/{slug}/reports/latest` — Report: report content, download links
- [ ] `GET /projects/{slug}/reports/history` — Report history
- [ ] `GET /projects/{slug}/questionnaires/history` — Questionnaire history

**Step 3: Fix any visual issues found**

Common issues to watch for:
- Pico adds padding to `<article>` elements — check if any `<article>` in analysis/detail.html looks too padded
- Pico styles `<fieldset>` and `<legend>` — check knowledge upload and dataset preview
- Pico styles nested `<section>` elements — watch for double-padding on nested sections (e.g., alert inside section)

**Step 4: Commit any fixes**

```bash
git add -u
git commit -m "fix(2.0F): resolve Pico CSS visual compatibility issues"
```

---

## Phase 2: Brand Rename (Tasks 5-6)

### Task 5: Rename product to 极光问卷

**Files:**
- Modify: `src/game_survey_workbench/templates/index.html:2,5`
- Modify: `tests/test_1_0_i18n.py:23`
- Test: `tests/test_pico_integration.py` (extend)

**Step 1: Write the failing test**

Append to `tests/test_pico_integration.py`:

```python
def test_brand_name_is_aurora_survey(client: TestClient):
    response = client.get("/")
    html = response.text
    assert "极光问卷" in html
    assert "游戏问卷研究工作台" not in html
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pico_integration.py::test_brand_name_is_aurora_survey -v`
Expected: FAIL — index.html still has 游戏问卷研究工作台

**Step 3: Update templates**

Edit `src/game_survey_workbench/templates/index.html`:
- Line 2: `{% block title %}游戏问卷研究工作台{% endblock %}` → `{% block title %}极光问卷{% endblock %}`
- Line 5: `<h1>游戏问卷研究工作台</h1>` → `<h1>极光问卷</h1>`

Note: `layout.html` was already updated in Task 1 (title default and nav-brand).

**Step 4: Update the old test that asserts the old brand name**

Edit `tests/test_1_0_i18n.py` line 23:
- `assert "游戏问卷研究工作台" in response.text` → `assert "极光问卷" in response.text`

**Step 5: Run tests to verify**

Run: `pytest tests/test_pico_integration.py::test_brand_name_is_aurora_survey tests/test_1_0_i18n.py::test_layout_nav_is_chinese -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/game_survey_workbench/templates/index.html tests/test_1_0_i18n.py tests/test_pico_integration.py
git commit -m "feat(2.0F): rebrand to 极光问卷 (Aurora Survey)"
```

---

### Task 6: Update index page tagline

**Files:**
- Modify: `src/game_survey_workbench/templates/index.html:6`

**Step 1: Update the tagline**

Edit `src/game_survey_workbench/templates/index.html` line 6:
- `<p>围绕项目上下文统一管理问卷设计、数据分析与报告生成。</p>` → `<p>智能问卷设计、数据分析与研究报告一站式工作台。</p>`

**Step 2: Run full test suite to verify no regressions**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass. No test asserts the exact tagline text.

**Step 3: Commit**

```bash
git add src/game_survey_workbench/templates/index.html
git commit -m "feat(2.0F): update tagline to match new brand identity"
```

---

## Phase 3: LLM Loading Spinner (Tasks 7-10)

### Task 7: Add CSS spinner animation

**Files:**
- Modify: `src/game_survey_workbench/static/app.css`
- Test: `tests/test_pico_integration.py` (extend)

**Step 1: Write the failing test**

Append to `tests/test_pico_integration.py`:

```python
def test_app_css_has_spinner_animation(client: TestClient):
    response = client.get("/static/app.css")
    css = response.text
    assert "@keyframes" in css
    assert "spinner" in css.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pico_integration.py::test_app_css_has_spinner_animation -v`
Expected: FAIL

**Step 3: Add spinner CSS**

Append to the end of `src/game_survey_workbench/static/app.css`:

```css
/* ── Loading spinner ──────────────────────────── */
@keyframes aurora-spin {
  to { transform: rotate(360deg); }
}

.btn-loading {
  pointer-events: none;
  opacity: 0.7;
}

.btn-loading::after {
  content: "";
  display: inline-block;
  width: 1em;
  height: 1em;
  margin-left: 0.5em;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  vertical-align: middle;
  animation: aurora-spin 0.6s linear infinite;
}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pico_integration.py::test_app_css_has_spinner_animation -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/static/app.css
git commit -m "feat(2.0F): add CSS spinner animation for loading states"
```

---

### Task 8: Add spinner JavaScript to layout

**Files:**
- Modify: `src/game_survey_workbench/templates/layout.html`
- Test: `tests/test_pico_integration.py` (extend)

**Step 1: Write the failing test**

Append to `tests/test_pico_integration.py`:

```python
def test_layout_includes_spinner_script(client: TestClient):
    response = client.get("/")
    html = response.text
    assert "data-loading-text" in html or "aurora-loading" in html or "<script>" in html


def test_script_handles_loading_attribute(client: TestClient):
    """The inline script must reference data-loading-text."""
    response = client.get("/")
    html = response.text
    assert "data-loading-text" in html
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pico_integration.py::test_layout_includes_spinner_script -v`
Expected: FAIL — no script tag in layout

**Step 3: Add the inline script**

Edit `src/game_survey_workbench/templates/layout.html`, add before `</body>`:

```html
<script>
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("button[data-loading-text]").forEach(function (btn) {
    btn.closest("form").addEventListener("submit", function () {
      btn.disabled = true;
      btn.textContent = btn.getAttribute("data-loading-text");
      btn.classList.add("btn-loading");
    });
  });
});
</script>
```

This script:
- Finds all buttons with `data-loading-text` attribute
- On their parent form's submit event: disables button, swaps text, adds spinner class
- No external dependencies, ~10 lines

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pico_integration.py::test_layout_includes_spinner_script tests/test_pico_integration.py::test_script_handles_loading_attribute -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/templates/layout.html
git commit -m "feat(2.0F): add inline spinner script for loading states"
```

---

### Task 9: Add data-loading-text to LLM-triggering buttons

**Files:**
- Modify: `src/game_survey_workbench/templates/questionnaires/detail.html:77,95`
- Modify: `src/game_survey_workbench/templates/analysis/detail.html:104,165,175`
- Modify: `src/game_survey_workbench/templates/coding_jobs/merge_review.html:46`
- Test: `tests/test_spinner_buttons.py`

**Step 1: Write the failing test**

Create `tests/test_spinner_buttons.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def client_with_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        session.add(ProjectRecord(slug="sp", name="Spinner Test"))
        session.add(
            QuestionnaireSpecVersion(
                project_slug="sp",
                version_id="v1",
                research_goal="test",
                markdown_spec="# Q\n\n1. Question",
            )
        )
        session.commit()
    with TestClient(create_app()) as test_client:
        yield test_client


def test_questionnaire_draft_button_has_loading_text(client: TestClient):
    client.post("/projects", json={"slug": "sp1", "name": "SP1"})
    response = client.get("/projects/sp1/questionnaires/latest")
    html = response.text
    assert 'data-loading-text=' in html


def test_questionnaire_refine_button_has_loading_text(client_with_project):
    response = client_with_project.get("/projects/sp/questionnaires/latest")
    html = response.text
    # Should have loading text on both draft and refine buttons
    assert html.count("data-loading-text=") >= 2


def test_analysis_buttons_have_loading_text(client: TestClient):
    client.post("/projects", json={"slug": "sp2", "name": "SP2"})
    csv_content = "Q1,Q2\nsingle_choice,free_text\nA,text\n"
    import io

    response = client.post(
        "/projects/sp2/datasets/import-form",
        files={"file": ("d.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        follow_redirects=True,
    )
    html = response.text
    # At least the text coding and insight buttons should have loading text
    if "data-loading-text=" in html:
        assert True
    else:
        # If the page redirected to analysis and has submit buttons, they should have loading text
        analysis_response = client.get("/projects/sp2/analysis/latest")
        html = analysis_response.text
        assert "data-loading-text=" in html


def test_non_llm_buttons_do_not_have_loading_text(client: TestClient):
    """Settings save, project create, etc. should NOT have spinners."""
    response = client.get("/")
    html = response.text
    # The create project button should NOT have data-loading-text
    # Find the create project form submit — it should not have loading text
    assert html.count("data-loading-text=") == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_spinner_buttons.py -v`
Expected: FAIL — no data-loading-text attributes on any buttons yet

**Step 3: Add data-loading-text to LLM buttons**

Edit `src/game_survey_workbench/templates/questionnaires/detail.html`:

Line 77 — change:
```html
    <button type="submit">生成草稿</button>
```
to:
```html
    <button type="submit" data-loading-text="正在生成草稿…">生成草稿</button>
```

Line 95 — change:
```html
    <button type="submit">改进草稿</button>
```
to:
```html
    <button type="submit" data-loading-text="正在改进草稿…">改进草稿</button>
```

Edit `src/game_survey_workbench/templates/analysis/detail.html`:

Line 104 — change:
```html
    <button type="submit">执行文本编码（所有开放题）</button>
```
to:
```html
    <button type="submit" data-loading-text="正在编码…">执行文本编码（所有开放题）</button>
```

Line 165 — change:
```html
    <button type="submit">{% if insight %}重新生成洞察{% else %}生成洞察{% endif %}</button>
```
to:
```html
    <button type="submit" data-loading-text="正在生成洞察…">{% if insight %}重新生成洞察{% else %}生成洞察{% endif %}</button>
```

Line 175 — change:
```html
    <button type="submit">生成报告</button>
```
to:
```html
    <button type="submit" data-loading-text="正在生成报告…">生成报告</button>
```

Edit `src/game_survey_workbench/templates/coding_jobs/merge_review.html`:

Line 46 — change:
```html
  <button type="submit">确认合并</button>
```
to:
```html
  <button type="submit" data-loading-text="正在合并…">确认合并</button>
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_spinner_buttons.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/templates/questionnaires/detail.html src/game_survey_workbench/templates/analysis/detail.html src/game_survey_workbench/templates/coding_jobs/merge_review.html tests/test_spinner_buttons.py
git commit -m "feat(2.0F): add loading text to all LLM-triggering form buttons"
```

---

### Task 10: Full regression test + north-star update

**Files:**
- Modify: `docs/plans/2026-03-15-game-survey-workbench-2.0-north-star.md`

**Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass (320+ existing + ~10 new = ~330+). Zero failures.

**Step 2: Run compile check**

Run: `python -m compileall src/game_survey_workbench`
Expected: All files compile successfully.

**Step 3: Update north-star roadmap**

Add to the "当前执行状态" section in `docs/plans/2026-03-15-game-survey-workbench-2.0-north-star.md`, after the 2.0E entry:

```markdown
- `2.0F 体验打磨套件`：已完成
  - 引入 Pico CSS v2（CDN），全站自动获得专业表单、表格和排版样式
  - `app.css` 从 ~327 行瘦身至 ~150 行，仅保留品牌色覆盖和自定义组件
  - 产品重命名为「极光问卷」（Aurora Survey），更新导航、标题和首页
  - 所有 LLM 触发表单（6 个）新增 loading spinner：按钮禁用 + 旋转动画 + 文字替换
  - 零 Python 路由改动，零后端变更
  - YYYY-MM-DD 最终验证：`pytest -v` 通过（NNN passed, 3 skipped），`python -m compileall src` 通过
```

(Replace YYYY-MM-DD and NNN with actual values at execution time.)

**Step 4: Commit**

```bash
git add docs/plans/2026-03-15-game-survey-workbench-2.0-north-star.md
git commit -m "docs: update 2.0 roadmap after experience polish suite (2.0F)"
```

---

## Codex Agent Execution Instructions

To execute this plan with Codex or another agent:

```
打开项目目录 C:\Users\69050\Documents\Playground

使用 superpowers:executing-plans 技能，逐任务执行以下计划：
docs/plans/2026-03-19-game-survey-workbench-2.0f-experience-polish.md

每个 Task 严格按 Step 顺序执行：写测试 → 跑失败 → 实现 → 跑通过 → 提交。
不要跳步骤，不要合并 Task。每个 commit 对应一个 Task。

Task 4 是手动视觉检查，如果你无法启动 dev server，跳过手动验证部分，但仍然运行 pytest 确保无回归。

最终 Task 10 必须：
1. pytest tests/ -v --tb=short 全部通过
2. python -m compileall src/game_survey_workbench 无错误
3. 更新 north-star 文档中的测试计数和日期
```
