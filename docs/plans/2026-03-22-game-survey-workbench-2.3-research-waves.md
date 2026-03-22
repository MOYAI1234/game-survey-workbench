# Game Survey Workbench 2.3 — Research Waves Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reframe each project as a long-lived research program with multiple named research waves, so questionnaire design, data analysis, and report generation all run against the current wave instead of implicitly reusing the latest project-wide artifacts.

**Architecture:** Add a `ResearchWave` model as the new execution boundary under `ProjectRecord`, then scope questionnaire versions, analysis runs, reports, and workflow progress to `wave_id`. Restructure the project UI so project-level pages manage durable context (brief, settings, shared knowledge selection), while wave-level pages handle concrete execution and history.

**Tech Stack:** FastAPI, SQLModel, SQLite, Jinja2 templates, existing workflow-state services, MarkItDown-based knowledge ingestion, pytest

---

## Approved Product Direction

- `Project` remains the durable container for one long-running research theme or business module.
- `Research Wave` is the new unit of execution, with a manual name like `1.1 版本问卷`, `商业化专项`, or `2026Q2 满意度追踪`.
- Entering a project should first show the current wave if one exists; otherwise the primary CTA is `新建一轮研究`.
- Questionnaire, analysis, and report pages should default to the current wave, not the latest artifact across the whole project.
- Project-level knowledge selection stays as a default pool; wave-level generation can additionally choose project history artifacts as references.
- The current `任务计划` placeholder should be replaced by real wave progress or removed until it becomes meaningful.
- Data upload belongs in the analysis flow, not as a peer of the top-level project workflow links.
- Knowledge-source display on questionnaire pages should show concise provenance, not long raw chunk bodies in the main UI.
- Knowledge upload should stop making users classify purposes twice across upload and conversion confirmation.

## Non-goals

- No multi-user collaboration or permission model
- No cross-project wave sharing
- No OCR pipeline for image PDFs
- No automatic wave naming or version-number enforcement
- No redesign of the underlying report/questionnaire generation prompts in this phase

---

### Task 1: Add Research Wave Persistence And Bootstrap

**Files:**
- Create: `src/game_survey_workbench/models/research_wave.py`
- Modify: `src/game_survey_workbench/db.py`
- Modify: `src/game_survey_workbench/models/__init__.py`
- Test: `tests/test_workspace_bootstrap.py`
- Test: `tests/test_projects.py`

**Step 1: Write the failing test**

```python
def test_create_db_and_tables_backfills_research_wave_table(tmp_path: Path):
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)

    engine = get_engine(tmp_path)
    with engine.connect() as connection:
        rows = list(connection.exec_driver_sql("PRAGMA table_info(researchwave)"))

    assert {row[1] for row in rows} >= {
        "id",
        "project_slug",
        "name",
        "status",
        "is_current",
        "created_at",
        "updated_at",
    }
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_workspace_bootstrap.py::test_create_db_and_tables_backfills_research_wave_table -v`
Expected: FAIL because `researchwave` does not exist yet.

**Step 3: Write minimal implementation**

```python
class ResearchWave(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_slug: str = Field(index=True)
    name: str
    goal_summary: str = ""
    status: str = "draft"
    is_current: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

- Import the new model in `db.py` so `SQLModel.metadata.create_all(...)` creates the table.
- Add a bootstrap helper that backfills the table for existing workspaces and keeps schema upgrades idempotent.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_workspace_bootstrap.py::test_create_db_and_tables_backfills_research_wave_table -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/research_wave.py src/game_survey_workbench/db.py src/game_survey_workbench/models/__init__.py tests/test_workspace_bootstrap.py tests/test_projects.py
git commit -m "feat: add research wave model"
```

---

### Task 2: Add Wave Service Helpers And Current-Wave Resolution

**Files:**
- Create: `src/game_survey_workbench/services/research_waves.py`
- Modify: `src/game_survey_workbench/routes/projects.py`
- Test: `tests/test_stage3a_project_enrichment.py`
- Test: `tests/test_projects.py`

**Step 1: Write the failing test**

```python
def test_create_research_wave_marks_newest_wave_as_current(tmp_path: Path):
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)

    first = create_research_wave(
        workspace_root=tmp_path,
        project_slug="demo",
        name="1.0 版本问卷",
    )
    second = create_research_wave(
        workspace_root=tmp_path,
        project_slug="demo",
        name="1.1 版本问卷",
    )

    assert first.is_current is False
    assert second.is_current is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_projects.py::test_create_research_wave_marks_newest_wave_as_current -v`
Expected: FAIL because the helper does not exist.

**Step 3: Write minimal implementation**

```python
def create_research_wave(*, workspace_root: Path, project_slug: str, name: str, goal_summary: str = "") -> ResearchWave:
    ...

def list_research_waves(*, workspace_root: Path, project_slug: str) -> list[ResearchWave]:
    ...

def get_current_research_wave(*, workspace_root: Path, project_slug: str) -> ResearchWave | None:
    ...

def set_current_research_wave(*, workspace_root: Path, project_slug: str, wave_id: int) -> ResearchWave:
    ...
```

- Ensure only one current wave exists per project.
- Keep wave selection logic in the service layer, not embedded in route handlers.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_projects.py -k research_wave -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/research_waves.py src/game_survey_workbench/routes/projects.py tests/test_projects.py tests/test_stage3a_project_enrichment.py
git commit -m "feat: add research wave services"
```

---

### Task 3: Restructure Project Home Into Project-Level Context Plus Wave Index

**Files:**
- Modify: `src/game_survey_workbench/routes/projects.py`
- Modify: `src/game_survey_workbench/templates/projects/detail.html`
- Modify: `src/game_survey_workbench/templates/layout.html`
- Test: `tests/test_stage3d_project_homepage.py`
- Test: `tests/test_ui_uplift.py`
- Test: `tests/test_1_0_shared_knowledge.py`

**Step 1: Write the failing test**

```python
def test_project_page_shows_current_wave_workspace_and_new_wave_cta(client):
    client.post("/projects", json={"slug": "demo", "name": "Demo"})
    create_research_wave(..., project_slug="demo", name="1.1 版本问卷")

    response = client.get("/projects/demo")

    assert "研究轮次工作台" in response.text
    assert "1.1 版本问卷" in response.text
    assert "新建一轮研究" in response.text
    assert "上传问卷数据" not in response.text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_stage3d_project_homepage.py::test_project_page_shows_current_wave_workspace_and_new_wave_cta -v`
Expected: FAIL because the project page still shows the old workflow layout.

**Step 3: Write minimal implementation**

- Move `项目配置` and `研究简报` above the workflow area.
- Replace the old `核心工作流` block with a `研究轮次工作台` section.
- Show:
  - current wave card
  - historical wave list
  - `新建一轮研究` button
- Remove the top-level dataset upload form from project detail.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_stage3d_project_homepage.py tests/test_ui_uplift.py tests/test_1_0_shared_knowledge.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/projects.py src/game_survey_workbench/templates/projects/detail.html src/game_survey_workbench/templates/layout.html tests/test_stage3d_project_homepage.py tests/test_ui_uplift.py tests/test_1_0_shared_knowledge.py
git commit -m "feat: redesign project home around research waves"
```

---

### Task 4: Add Wave Creation, Selection, And Wave-Level Landing Page

**Files:**
- Modify: `src/game_survey_workbench/routes/projects.py`
- Create: `src/game_survey_workbench/templates/projects/wave_detail.html`
- Test: `tests/test_stage5_navigation.py`
- Test: `tests/test_stage5a_project_form.py`
- Test: `tests/test_stage20_project_knowledge_selection_routes.py`

**Step 1: Write the failing test**

```python
def test_create_wave_form_redirects_to_wave_workspace(client):
    client.post("/projects", json={"slug": "demo", "name": "Demo"})

    response = client.post(
        "/projects/demo/waves/create",
        data={"name": "商业化专项", "goal_summary": "验证 1.1 版本商业化体验"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("/projects/demo/waves/1")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_stage5a_project_form.py::test_create_wave_form_redirects_to_wave_workspace -v`
Expected: FAIL with 404 because the route does not exist.

**Step 3: Write minimal implementation**

- Add routes to:
  - create a wave
  - switch current wave
  - render `/projects/{project_slug}/waves/{wave_id}`
- The wave page should show:
  - wave name
  - goal summary
  - links to wave-specific questionnaire / analysis / report pages
  - compact history links for this wave only

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_stage5_navigation.py tests/test_stage5a_project_form.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/projects.py src/game_survey_workbench/templates/projects/wave_detail.html tests/test_stage5_navigation.py tests/test_stage5a_project_form.py tests/test_stage20_project_knowledge_selection_routes.py
git commit -m "feat: add research wave workspace routes"
```

---

### Task 5: Scope Questionnaire Versions To Waves And Clean Up Knowledge Basis Display

**Files:**
- Modify: `src/game_survey_workbench/models/questionnaire.py`
- Modify: `src/game_survey_workbench/routes/questionnaires.py`
- Modify: `src/game_survey_workbench/services/questionnaires.py`
- Modify: `src/game_survey_workbench/templates/questionnaires/detail.html`
- Modify: `src/game_survey_workbench/templates/questionnaires/history.html`
- Test: `tests/test_questionnaire_routes.py`
- Test: `tests/test_questionnaire_service.py`
- Test: `tests/test_stage5b_questionnaire_page.py`
- Test: `tests/test_questionnaire_download.py`

**Step 1: Write the failing test**

```python
def test_questionnaire_latest_page_is_scoped_to_current_wave(client, seeded_workspace):
    wave_one = create_research_wave(..., name="1.0 版本问卷")
    wave_two = create_research_wave(..., name="1.1 版本问卷")
    save_questionnaire_draft(..., wave_id=wave_one.id, markdown_spec="# Wave 1")
    save_questionnaire_draft(..., wave_id=wave_two.id, markdown_spec="# Wave 2")

    response = client.get("/projects/demo/questionnaires/latest")

    assert "Wave 2" in response.text
    assert "Wave 1" not in response.text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_stage5b_questionnaire_page.py::test_questionnaire_latest_page_is_scoped_to_current_wave -v`
Expected: FAIL because questionnaire records are still project-wide.

**Step 3: Write minimal implementation**

- Add `wave_id` to `QuestionnaireSpecVersion`.
- Update save/load/list/diff helpers to filter by wave.
- Change questionnaire detail page to:
  - show current wave context
  - treat `最新草稿` as “latest in this wave”
  - collapse provenance into short cards: title, pool, short excerpt
  - remove long `Knowledge Basis` body from the main reading flow

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_questionnaire_routes.py tests/test_questionnaire_service.py tests/test_stage5b_questionnaire_page.py tests/test_questionnaire_download.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/questionnaire.py src/game_survey_workbench/routes/questionnaires.py src/game_survey_workbench/services/questionnaires.py src/game_survey_workbench/templates/questionnaires/detail.html src/game_survey_workbench/templates/questionnaires/history.html tests/test_questionnaire_routes.py tests/test_questionnaire_service.py tests/test_stage5b_questionnaire_page.py tests/test_questionnaire_download.py
git commit -m "feat: scope questionnaires to research waves"
```

---

### Task 6: Scope Analysis And Reports To Waves And Move Dataset Upload Into Analysis

**Files:**
- Modify: `src/game_survey_workbench/models/analysis_run.py`
- Modify: `src/game_survey_workbench/models/reporting.py`
- Modify: `src/game_survey_workbench/routes/datasets.py`
- Modify: `src/game_survey_workbench/routes/reports.py`
- Modify: `src/game_survey_workbench/templates/analysis/detail.html`
- Modify: `src/game_survey_workbench/templates/reports/detail.html`
- Test: `tests/test_analysis_run.py`
- Test: `tests/test_stage5c_report_view.py`
- Test: `tests/test_report_download.py`
- Test: `tests/test_end_to_end_smoke.py`

**Step 1: Write the failing test**

```python
def test_dataset_upload_belongs_to_wave_analysis_workspace(client):
    wave = create_research_wave(..., name="1.1 版本问卷")

    response = client.get(f"/projects/demo/waves/{wave.id}/analysis")

    assert "上传问卷数据" in response.text
    assert "导入数据" in response.text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_analysis_run.py::test_dataset_upload_belongs_to_wave_analysis_workspace -v`
Expected: FAIL because upload still lives on the project page.

**Step 3: Write minimal implementation**

- Add `wave_id` to `AnalysisRunRecord` and `ReportRecord`.
- Resolve “latest analysis/report” within the current wave only.
- Move the dataset upload form into the analysis template for the active wave.
- Keep report generation tied to the analysis run in the same wave.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_analysis_run.py tests/test_stage5c_report_view.py tests/test_report_download.py tests/test_end_to_end_smoke.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/analysis_run.py src/game_survey_workbench/models/reporting.py src/game_survey_workbench/routes/datasets.py src/game_survey_workbench/routes/reports.py src/game_survey_workbench/templates/analysis/detail.html src/game_survey_workbench/templates/reports/detail.html tests/test_analysis_run.py tests/test_stage5c_report_view.py tests/test_report_download.py tests/test_end_to_end_smoke.py
git commit -m "feat: scope analysis and reports to research waves"
```

---

### Task 7: Replace Task Plan Placeholder With Real Wave Progress

**Files:**
- Modify: `src/game_survey_workbench/models/task_plan.py`
- Modify: `src/game_survey_workbench/routes/projects.py`
- Modify: `src/game_survey_workbench/templates/projects/detail.html`
- Modify: `src/game_survey_workbench/services/workflow_state.py`
- Test: `tests/test_stage6a_workflow_state.py`
- Test: `tests/test_stage6f_workflow_display.py`
- Test: `tests/test_stage3d_project_homepage.py`

**Step 1: Write the failing test**

```python
def test_project_page_shows_wave_progress_instead_of_task_plan_placeholder(client):
    wave = create_research_wave(..., name="1.1 版本问卷")

    response = client.get("/projects/demo")

    assert "当前轮次进度" in response.text
    assert "任务计划" not in response.text
    assert "当前版本不会自动生成任务计划" not in response.text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_stage3d_project_homepage.py::test_project_page_shows_wave_progress_instead_of_task_plan_placeholder -v`
Expected: FAIL because the old task-plan placeholder is still rendered.

**Step 3: Write minimal implementation**

- Stop surfacing `TaskPlanRecord` on the project detail page.
- Reuse workflow-state information to show wave progress:
  - question draft present
  - dataset imported
  - coding complete
  - insights complete
  - report generated
- Keep `TaskPlanRecord` untouched unless you confirm it is truly dead code after migration.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_stage6a_workflow_state.py tests/test_stage6f_workflow_display.py tests/test_stage3d_project_homepage.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/task_plan.py src/game_survey_workbench/routes/projects.py src/game_survey_workbench/templates/projects/detail.html src/game_survey_workbench/services/workflow_state.py tests/test_stage6a_workflow_state.py tests/test_stage6f_workflow_display.py tests/test_stage3d_project_homepage.py
git commit -m "feat: replace project task plan placeholder with wave progress"
```

---

### Task 8: Simplify Knowledge Upload Purpose Selection

**Files:**
- Modify: `src/game_survey_workbench/routes/knowledge.py`
- Modify: `src/game_survey_workbench/templates/knowledge/convert_preview.html`
- Test: `tests/test_knowledge_convert_routes.py`
- Test: `tests/test_knowledge_routes.py`

**Step 1: Write the failing test**

```python
def test_convert_preview_preserves_upload_purposes_without_reasking(client):
    response = client.post(
        "/knowledge/upload",
        files={"file": ("methods.docx", handle, mime)},
        data={"purposes": ["analysis"]},
        follow_redirects=True,
    )

    assert 'name="purposes"' in response.text
    assert 'checked' not in response.text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_knowledge_convert_routes.py::test_convert_preview_preserves_upload_purposes_without_reasking -v`
Expected: FAIL because the flow still asks users to choose purposes again.

**Step 3: Write minimal implementation**

- Choose one consistent behavior:
  - either first step = file only, second step = all metadata
  - or first step captures purposes and second step preserves them as hidden inputs
- For this phase, prefer preserving first-step purposes as hidden values and rendering them read-only in preview.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_knowledge_convert_routes.py tests/test_knowledge_routes.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/knowledge.py src/game_survey_workbench/templates/knowledge/convert_preview.html tests/test_knowledge_convert_routes.py tests/test_knowledge_routes.py
git commit -m "feat: simplify knowledge upload purpose selection"
```

---

### Task 9: Full Regression Verification And Documentation Cleanup

**Files:**
- Modify: `docs/product-roadmap.md`
- Modify: `docs/plans/2026-03-22-game-survey-workbench-2.3-research-waves.md`
- Test: `tests/`

**Step 1: Write the failing verification checklist**

```text
- project homepage shows wave workspace
- wave creation works
- latest questionnaire/analysis/report resolve within current wave
- stale knowledge records are cleaned
- epub upload still works
```

**Step 2: Run targeted suites before full regression**

Run: `pytest tests/test_projects.py tests/test_questionnaire_routes.py tests/test_analysis_run.py tests/test_report_download.py tests/test_knowledge_routes.py -v`
Expected: PASS

**Step 3: Run full verification**

Run: `pytest tests/ -v --tb=short`
Expected: PASS with no new failures introduced by wave scoping.

Run: `python -m compileall src/game_survey_workbench`
Expected: no compile errors.

**Step 4: Update roadmap and plan status**

- Mark `2.3` as “plan written, pending execution”.
- Advance `docs/product-roadmap.md` so the next planning line becomes `2.4`.

**Step 5: Commit**

```bash
git add docs/product-roadmap.md docs/plans/2026-03-22-game-survey-workbench-2.3-research-waves.md
git commit -m "docs: finalize 2.3 research waves plan"
```

