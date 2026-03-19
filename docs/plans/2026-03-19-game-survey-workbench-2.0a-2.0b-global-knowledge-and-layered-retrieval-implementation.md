# Game Survey Workbench 2.0A/2.0B Global Knowledge And Layered Retrieval Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the 2.0 knowledge experience into a real global library with project-level selected documents and dual-pool retrieval inside that selected set.

**Architecture:** Keep the current local monolith and existing `KnowledgeDocument` store, but add a durable project-to-document selection layer. Move project knowledge behavior from "project page uploads shared docs" to "project selects shared docs," then change retrieval so questionnaire and insight flows search only the selected set and split results into a method pool and a domain pool.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, Jinja2, pytest, existing TF-IDF retrieval store

---

## Assumptions

- `docs/plans/2026-03-15-game-survey-workbench-2.0-north-star.md` is the source of truth for 2.0 direction.
- This plan intentionally combines `2.0A` and `2.0B`.
- The selected-document relationship is the primary project knowledge mechanism.
- The first release includes basic hit feedback but not analytics dashboards, query expansion, or embeddings.

## Task 1: Add explicit project knowledge selection persistence

**Files:**
- Create: `src/game_survey_workbench/models/project_knowledge_selection.py`
- Create: `src/game_survey_workbench/services/project_knowledge.py`
- Modify: `src/game_survey_workbench/db.py`
- Create: `tests/test_project_knowledge_selection.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.project_knowledge import (
    list_selected_knowledge_document_ids,
    replace_project_knowledge_selection,
)
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file


def test_replace_project_knowledge_selection_persists_selected_document_ids(tmp_path: Path):
    create_project(
        ProjectCreate(slug="demo", name="Demo"),
        workspace_root=tmp_path,
    )
    first = tmp_path / "doc-one.md"
    first.write_text(
        "---\n"
        "title: Method Doc\n"
        "doc_type: guide\n"
        "stage:\n"
        "  - design\n"
        "---\n"
        "Method content.\n",
        encoding="utf-8",
    )
    second = tmp_path / "doc-two.md"
    second.write_text(
        "---\n"
        "title: Domain Doc\n"
        "doc_type: research\n"
        "stage:\n"
        "  - analysis\n"
        "---\n"
        "Domain content.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(first, project_root=tmp_path)
    ingest_knowledge_file(second, project_root=tmp_path)

    selected = replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="demo",
        knowledge_document_ids=[1, 2],
    )

    assert len(selected) == 2
    assert list_selected_knowledge_document_ids(
        workspace_root=tmp_path,
        project_slug="demo",
    ) == [1, 2]
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_project_knowledge_selection.py -v`

Expected:
- FAIL because the model and service do not exist yet

**Step 3: Write the minimal implementation**

Create a new SQLModel table:

```python
class ProjectKnowledgeSelection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_slug: str = Field(index=True)
    knowledge_document_id: int = Field(index=True)
    selected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

Create service helpers:

```python
def list_selected_knowledge_document_ids(*, workspace_root: Path, project_slug: str) -> list[int]:
    ...


def replace_project_knowledge_selection(
    *,
    workspace_root: Path,
    project_slug: str,
    knowledge_document_ids: list[int],
) -> list[ProjectKnowledgeSelection]:
    ...
```

Implementation rules:

- validate that the project exists
- replace the full selection set in one operation
- deduplicate incoming ids while preserving stable order
- store only real `KnowledgeDocument` ids

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_project_knowledge_selection.py -v`

Expected:
- PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/project_knowledge_selection.py src/game_survey_workbench/services/project_knowledge.py src/game_survey_workbench/db.py tests/test_project_knowledge_selection.py
git commit -m "feat: add project knowledge selection persistence"
```

## Task 2: Upgrade the global knowledge page into a management page with filtering

**Files:**
- Modify: `src/game_survey_workbench/routes/knowledge.py`
- Modify: `src/game_survey_workbench/templates/knowledge/detail.html`
- Create: `tests/test_stage20_knowledge_library_page.py`
- Modify: `tests/test_1_0_shared_knowledge.py`

**Step 1: Write the failing tests**

```python
def test_knowledge_page_filters_documents_by_stage_and_type(client, tmp_path):
    ...
    response = client.get("/knowledge?stage=design&doc_type=guide")
    html = response.text
    assert "方法论文档" in html
    assert "领域文档" not in html


def test_knowledge_page_shows_global_management_language(client):
    response = client.get("/knowledge")
    html = response.text
    assert "共享知识库管理" in html
    assert "筛选" in html
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage20_knowledge_library_page.py tests/test_1_0_shared_knowledge.py -v`

Expected:
- FAIL because the current page is a simple list/upload page with no filtering controls

**Step 3: Write the minimal implementation**

Update `/knowledge` so it:

- accepts optional query params like `search`, `stage`, `doc_type`, and `tag`
- filters `KnowledgeDocument` rows before rendering
- keeps upload capability intact
- updates copy to make the page clearly global and management-oriented

Template changes should add:

- filter inputs
- metadata display for `doc_type`, `stages`, `tags`, and `priority`
- more explicit page heading language

Do not add delete/edit actions in this task.

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage20_knowledge_library_page.py tests/test_1_0_shared_knowledge.py -v`

Expected:
- PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/knowledge.py src/game_survey_workbench/templates/knowledge/detail.html tests/test_stage20_knowledge_library_page.py tests/test_1_0_shared_knowledge.py
git commit -m "feat: upgrade shared knowledge page into a global management view"
```

## Task 3: Replace project knowledge upload-first UI with project knowledge selection

**Files:**
- Modify: `src/game_survey_workbench/routes/projects.py`
- Modify: `src/game_survey_workbench/templates/projects/detail.html`
- Modify: `src/game_survey_workbench/services/project_knowledge.py`
- Create: `tests/test_stage20_project_knowledge_selection_routes.py`
- Modify: `tests/test_stage5a_upload_forms.py`
- Modify: `tests/test_stage3d_project_homepage.py`

**Step 1: Write the failing tests**

```python
def test_project_page_shows_selected_knowledge_and_selection_form(client, tmp_path):
    ...
    response = client.get("/projects/demo")
    html = response.text
    assert "项目知识选择" in html
    assert 'name="knowledge_document_ids"' in html
    assert "当前已选知识" in html


def test_project_knowledge_selection_form_replaces_selected_documents(client, tmp_path):
    ...
    response = client.post(
        "/projects/demo/knowledge-selection",
        data={"knowledge_document_ids": ["1", "2"]},
        follow_redirects=False,
    )
    assert response.status_code == 303
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage20_project_knowledge_selection_routes.py tests/test_stage5a_upload_forms.py tests/test_stage3d_project_homepage.py -v`

Expected:
- FAIL because the project page still exposes the upload form as the primary knowledge action

**Step 3: Write the minimal implementation**

Update project detail flow so it:

- loads all global `KnowledgeDocument` rows for display
- loads the selected ids for the project
- renders a selection form with checkboxes
- shows a separate section for currently selected knowledge
- links back to `/knowledge` for global management

Add a new route:

```python
@router.post("/projects/{project_slug}/knowledge-selection")
def save_project_knowledge_selection(...):
    ...
```

Behavior rules:

- selection form replaces the full current selection
- empty submission is allowed and clears the project selection
- project page copy should explain that uploads now belong in the global knowledge library

Do not keep the project-local knowledge upload form in the page template.

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage20_project_knowledge_selection_routes.py tests/test_stage5a_upload_forms.py tests/test_stage3d_project_homepage.py -v`

Expected:
- PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/projects.py src/game_survey_workbench/templates/projects/detail.html src/game_survey_workbench/services/project_knowledge.py tests/test_stage20_project_knowledge_selection_routes.py tests/test_stage5a_upload_forms.py tests/test_stage3d_project_homepage.py
git commit -m "feat: add project knowledge selection and remove upload-first project flow"
```

## Task 4: Add selected-set dual-pool retrieval

**Files:**
- Modify: `src/game_survey_workbench/retrieval/store.py`
- Modify: `src/game_survey_workbench/services/knowledge_ingest.py`
- Modify: `src/game_survey_workbench/services/project_knowledge.py`
- Modify: `tests/test_retrieval_service.py`
- Create: `tests/test_stage20_layered_retrieval.py`

**Step 1: Write the failing tests**

```python
def test_retrieve_project_knowledge_only_uses_selected_documents(tmp_path):
    ...
    results = retrieve_project_knowledge(
        workspace_root=tmp_path,
        project_slug="demo",
        query="pricing clarity",
        stages=["design"],
    )
    assert all(item["document_title"] != "Unselected Doc" for item in results)


def test_retrieve_project_knowledge_combines_method_pool_and_domain_pool(tmp_path):
    ...
    results = retrieve_project_knowledge(
        workspace_root=tmp_path,
        project_slug="demo",
        query="season pass value",
        stages=["design"],
    )
    assert any(item["retrieval_pool"] == "method" for item in results)
    assert any(item["retrieval_pool"] == "domain" for item in results)
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_retrieval_service.py tests/test_stage20_layered_retrieval.py -v`

Expected:
- FAIL because retrieval still depends on `knowledge_pack` and single-pool query logic

**Step 3: Write the minimal implementation**

Update the retrieval layer so it can:

- filter chunks by selected knowledge document ids
- derive method-pool candidates from matching `stages` or high `priority`
- derive domain-pool candidates from eligible `doc_type` values
- rank Pool B with the existing TF-IDF logic
- bound Pool A and Pool B separately
- merge and deduplicate results
- annotate each result with `retrieval_pool`

Suggested shape:

```python
def query_layered(
    self,
    query: str,
    *,
    selected_document_titles: list[str],
    task_stages: list[str],
    top_method_k: int = 3,
    top_domain_k: int = 5,
) -> list[dict]:
    ...
```

Then update `retrieve_project_knowledge()` to:

- load project selected ids
- map ids to `KnowledgeDocument` titles
- call the layered retrieval path instead of the old `knowledge_pack` path

Keep the current `retrieve_knowledge()` API available for non-2.0 callers unless a failing test proves it should be removed.

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_retrieval_service.py tests/test_stage20_layered_retrieval.py -v`

Expected:
- PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/retrieval/store.py src/game_survey_workbench/services/knowledge_ingest.py src/game_survey_workbench/services/project_knowledge.py tests/test_retrieval_service.py tests/test_stage20_layered_retrieval.py
git commit -m "feat: add selected-set layered retrieval for projects"
```

## Task 5: Fail clearly when a project has no selected knowledge or no layered hits

**Files:**
- Modify: `src/game_survey_workbench/errors.py`
- Modify: `src/game_survey_workbench/services/questionnaires.py`
- Modify: `src/game_survey_workbench/services/insights.py`
- Modify: `src/game_survey_workbench/routes/questionnaires.py`
- Modify: `src/game_survey_workbench/routes/insights.py`
- Modify: `tests/test_questionnaire_service.py`
- Modify: `tests/test_insights_service.py`
- Modify: `tests/test_questionnaire_routes.py`
- Modify: `tests/test_insights_routes.py`

**Step 1: Write the failing tests**

```python
import pytest

from game_survey_workbench.errors import NoKnowledgeSelectedError, NoKnowledgeMatchedError


def test_generate_questionnaire_draft_rejects_projects_without_selected_knowledge(tmp_path):
    ...
    with pytest.raises(NoKnowledgeSelectedError):
        generate_questionnaire_draft(...)


def test_generate_analysis_insights_rejects_when_layered_retrieval_returns_no_hits(tmp_path):
    ...
    with pytest.raises(NoKnowledgeMatchedError):
        generate_analysis_insights(...)
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_questionnaire_service.py tests/test_insights_service.py tests/test_questionnaire_routes.py tests/test_insights_routes.py -v`

Expected:
- FAIL because current services silently retry with broader or empty retrieval behavior

**Step 3: Write the minimal implementation**

Add typed exceptions such as:

```python
class NoKnowledgeSelectedError(ValueError):
    pass
```

Then change questionnaire and insight generation so they:

- detect whether the project has zero selected documents
- fail clearly instead of falling back to global-ish behavior
- allow Pool A or Pool B to be empty individually
- fail only when both pools produce no final retrieval context

Update routes to map these errors to explicit UI/API feedback.

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_questionnaire_service.py tests/test_insights_service.py tests/test_questionnaire_routes.py tests/test_insights_routes.py -v`

Expected:
- PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/errors.py src/game_survey_workbench/services/questionnaires.py src/game_survey_workbench/services/insights.py src/game_survey_workbench/routes/questionnaires.py src/game_survey_workbench/routes/insights.py tests/test_questionnaire_service.py tests/test_insights_service.py tests/test_questionnaire_routes.py tests/test_insights_routes.py
git commit -m "fix: make 2.0 knowledge selection and retrieval failures explicit"
```

## Task 6: Surface basic retrieval-hit feedback in questionnaire and analysis pages

**Files:**
- Modify: `src/game_survey_workbench/services/questionnaires.py`
- Modify: `src/game_survey_workbench/services/insights.py`
- Modify: `src/game_survey_workbench/templates/questionnaires/detail.html`
- Modify: `src/game_survey_workbench/templates/analysis/detail.html`
- Modify: `tests/test_stage5b_questionnaire_page.py`
- Modify: `tests/test_stage5b_analysis_dashboard.py`
- Modify: `tests/test_questionnaire_service.py`
- Modify: `tests/test_insights_service.py`

**Step 1: Write the failing tests**

```python
def test_questionnaire_page_shows_retrieval_pool_metadata_for_used_knowledge(client, tmp_path):
    ...
    response = client.get("/projects/demo/questionnaires/latest")
    html = response.text
    assert "方法论池" in html
    assert "领域知识池" in html


def test_analysis_page_shows_used_knowledge_snippets_for_insight_basis(client, tmp_path):
    ...
    response = client.get("/projects/demo/analysis/latest")
    html = response.text
    assert "本次知识依据" in html
    assert "document title" in html
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage5b_questionnaire_page.py tests/test_stage5b_analysis_dashboard.py tests/test_questionnaire_service.py tests/test_insights_service.py -v`

Expected:
- FAIL because templates only show basic snippet titles and do not expose pool metadata

**Step 3: Write the minimal implementation**

Make sure retrieval results persisted into questionnaire versions and insight citations include:

- `document_title`
- `content`
- `retrieval_pool`

Then update UI templates to show a simple basis block, for example:

- document title
- pool label (`方法论池` / `领域知识池`)
- snippet preview

Keep the rendering simple. Do not add charts, percentages, or scoring explanations.

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage5b_questionnaire_page.py tests/test_stage5b_analysis_dashboard.py tests/test_questionnaire_service.py tests/test_insights_service.py -v`

Expected:
- PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/questionnaires.py src/game_survey_workbench/services/insights.py src/game_survey_workbench/templates/questionnaires/detail.html src/game_survey_workbench/templates/analysis/detail.html tests/test_stage5b_questionnaire_page.py tests/test_stage5b_analysis_dashboard.py tests/test_questionnaire_service.py tests/test_insights_service.py
git commit -m "feat: show basic layered retrieval feedback in questionnaire and analysis views"
```

## Task 7: Run full regression and update 2.0 roadmap status

**Files:**
- Modify: `docs/plans/2026-03-15-game-survey-workbench-2.0-north-star.md`

**Step 1: Update roadmap status text**

Add a short status note for:

- `2.0A Global Knowledge Library`
- `2.0B Layered Retrieval Strategy`

Record that these are in implementation or completed, depending on the actual execution result.

**Step 2: Run verification**

Run:

```bash
.venv/Scripts/python.exe -m pytest -v
.venv/Scripts/python.exe -m compileall src
```

Expected:
- full suite passes
- compile check passes

**Step 3: Manually verify**

Confirm:

- `/knowledge` behaves like a global management page
- project pages allow explicit document selection
- questionnaire generation fails clearly when no project knowledge is selected
- questionnaire and insights use only selected project knowledge
- output pages show basic hit feedback with method/domain pool labels

**Step 4: Commit**

```bash
git add docs/plans/2026-03-15-game-survey-workbench-2.0-north-star.md
git commit -m "docs: update 2.0 roadmap after global knowledge and layered retrieval"
```

---

## Verification Checklist Before Any Completion Claim

- Run: `.venv/Scripts/python.exe -m pytest tests/test_project_knowledge_selection.py tests/test_stage20_knowledge_library_page.py tests/test_stage20_project_knowledge_selection_routes.py tests/test_stage20_layered_retrieval.py -v`
- Run: `.venv/Scripts/python.exe -m pytest -v`
- Run: `.venv/Scripts/python.exe -m compileall src`
- Manually confirm:
  - global knowledge management and project knowledge selection are clearly separated
  - no project output uses unselected global knowledge
  - method-pool knowledge can appear even when lexical overlap is weak
  - domain-pool knowledge still responds to query relevance
  - UI explains which knowledge snippets were used

## Notes

- Do not silently widen retrieval to all workspace knowledge when selection is empty.
- Keep the implementation small enough that later query expansion and embeddings can layer on top without redoing the persistence model.
- Update or replace old upload-first tests rather than preserving the wrong 1.0 semantics.
