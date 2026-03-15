# Game Survey Workbench 1.0 Knowledge Closeout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make shared knowledge understandable and usable in 1.0 by adding a homepage-first shared knowledge entry, purpose-based upload, visible knowledge inventory, and graceful no-knowledge fallback for the core workflows.

**Architecture:** Keep the existing workspace-level knowledge storage and retrieval model. Add a lightweight shared knowledge page and route, reframe project pages to reference the shared library, inject upload-purpose metadata before ingest, and relax hard no-match failures into explicit fallback behavior. Limit changes to templates, routes, and the smallest necessary service helpers.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLModel, existing local vector store and Markdown parsing pipeline.

**Design Doc:** `docs/plans/2026-03-15-game-survey-workbench-1.0-knowledge-closeout-design.md`

---

### Task 1: Add Shared Knowledge Summary To The Homepage

**Files:**
- Modify: `src/game_survey_workbench/routes/ui.py`
- Modify: `src/game_survey_workbench/templates/layout.html`
- Modify: `src/game_survey_workbench/templates/index.html`
- Test: `tests/test_1_0_shared_knowledge.py`

**Step 1: Write the failing test**

Create `tests/test_1_0_shared_knowledge.py` with a homepage test that:

- loads `/`
- expects `共享知识库` in the navigation or main content
- expects a shared knowledge summary block
- expects empty-state copy that explains knowledge is shared across projects

**Step 2: Run the test to verify it fails**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/test_1_0_shared_knowledge.py::test_homepage_shows_shared_knowledge_entry --tb=short -q
```

Expected: FAIL because the homepage does not expose a shared knowledge entry yet.

**Step 3: Write the minimal implementation**

- Extend `ui.py` to load a small shared-knowledge summary from the database.
- Pass summary data into `index.html`.
- Add a `共享知识库` navigation link in `layout.html`.
- Add a homepage section showing:
  - total count
  - recent documents
  - link to `/knowledge`

**Step 4: Run the test again**

Expected: PASS

**Step 5: Run the full suite**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest --tb=short -q
```

**Step 6: Commit**

```bash
git add src/game_survey_workbench/routes/ui.py src/game_survey_workbench/templates/layout.html src/game_survey_workbench/templates/index.html tests/test_1_0_shared_knowledge.py
git commit -m "fix(1.0): add homepage-first shared knowledge entry"
```

---

### Task 2: Add A Lightweight Shared Knowledge Page

**Files:**
- Create: `src/game_survey_workbench/templates/knowledge/detail.html`
- Create or Modify: `src/game_survey_workbench/routes/knowledge.py` or extend `src/game_survey_workbench/routes/projects.py`
- Modify: `src/game_survey_workbench/app.py`
- Test: `tests/test_1_0_shared_knowledge.py`

**Step 1: Write the failing test**

Add tests that:

- GET `/knowledge`
- expect status `200`
- expect `共享知识库`
- expect a list container for existing documents
- expect upload form labels in Chinese

**Step 2: Run the test to verify it fails**

Expected: FAIL because no `/knowledge` page exists.

**Step 3: Write the minimal implementation**

- Add a page route for `/knowledge`.
- Render a minimal template with:
  - title
  - explanatory copy saying knowledge is shared across projects
  - list of current documents
  - upload form
  - success/error alert area

Document rows should show at least:

- title
- purpose labels
- source filename or source path tail

**Step 4: Run the test again**

Expected: PASS

**Step 5: Run the full suite**

**Step 6: Commit**

```bash
git add src/game_survey_workbench/templates/knowledge/detail.html src/game_survey_workbench/routes/knowledge.py src/game_survey_workbench/app.py tests/test_1_0_shared_knowledge.py
git commit -m "fix(1.0): add shared knowledge page"
```

---

### Task 3: Support Purpose-Based Upload Without Requiring Front Matter

**Files:**
- Modify: `src/game_survey_workbench/templates/knowledge/detail.html`
- Modify: `src/game_survey_workbench/templates/projects/detail.html`
- Modify: `src/game_survey_workbench/routes/projects.py`
- Modify: `src/game_survey_workbench/routes/knowledge.py` if created
- Modify: `src/game_survey_workbench/services/knowledge_ingest.py`
- Test: `tests/test_1_0_shared_knowledge.py`

**Step 1: Write the failing tests**

Add tests that:

- upload a Markdown file without front matter but with purpose selections
- verify upload succeeds
- verify the stored knowledge document can later be listed with the selected purpose labels
- verify a document uploaded with `问卷设计` is persisted with design-stage metadata

**Step 2: Run them to verify they fail**

Expected: FAIL because current upload only accepts a file and does not map purpose selections into metadata.

**Step 3: Write the minimal implementation**

- Add multi-select fields to the upload form:
  - `问卷设计`
  - `问卷分析`
  - `报告写作`
- Extend the upload route to accept the selected purpose list.
- Before ingesting, synthesize effective metadata from the selections.
- Preserve front matter compatibility, but let UI purpose choices override absent metadata.

Keep the data flow minimal:

- create a small helper that merges:
  - uploaded file content
  - selected purposes
  - inferred title fallback
- pass the merged Markdown content into the existing ingest pipeline

**Step 4: Run the tests again**

Expected: PASS

**Step 5: Run the full suite**

**Step 6: Commit**

```bash
git add src/game_survey_workbench/templates/knowledge/detail.html src/game_survey_workbench/templates/projects/detail.html src/game_survey_workbench/routes/projects.py src/game_survey_workbench/routes/knowledge.py src/game_survey_workbench/services/knowledge_ingest.py tests/test_1_0_shared_knowledge.py
git commit -m "fix(1.0): add purpose-based shared knowledge upload"
```

---

### Task 4: Reframe The Project Page Around Shared Knowledge

**Files:**
- Modify: `src/game_survey_workbench/templates/projects/detail.html`
- Modify: `src/game_survey_workbench/routes/projects.py`
- Test: `tests/test_1_0_shared_knowledge.py`

**Step 1: Write the failing test**

Add a project-page test that:

- GETs `/projects/<slug>`
- expects Chinese copy explaining the project uses the shared knowledge library
- expects a link to `/knowledge`
- does not imply project-private ownership

**Step 2: Run the test to verify it fails**

Expected: FAIL because the project page still frames knowledge upload as project-local.

**Step 3: Write the minimal implementation**

- Replace the current section heading and help text.
- Keep a shortcut upload form only if it explicitly says it uploads to the shared library.
- Add a small summary:
  - total shared documents
  - link to manage/view all shared documents

**Step 4: Run the tests again**

Expected: PASS

**Step 5: Run the full suite**

**Step 6: Commit**

```bash
git add src/game_survey_workbench/templates/projects/detail.html src/game_survey_workbench/routes/projects.py tests/test_1_0_shared_knowledge.py
git commit -m "fix(1.0): reframe project knowledge as shared library usage"
```

---

### Task 5: Make Questionnaire Generation Degrade Gracefully When No Knowledge Matches

**Files:**
- Modify: `src/game_survey_workbench/services/questionnaires.py`
- Modify: `src/game_survey_workbench/routes/questionnaires.py`
- Modify: `src/game_survey_workbench/templates/questionnaires/detail.html`
- Test: `tests/test_stage5b_questionnaire_page.py`
- Test: `tests/test_1_0_shared_knowledge.py`

**Step 1: Write the failing tests**

Add tests that:

- create a project with no knowledge documents
- submit the questionnaire draft form
- verify the request redirects back successfully instead of hard-failing
- verify a draft is created
- verify the page displays a Chinese fallback notice

Also add a test for “knowledge exists but none match design stage” with the same expected behavior.

**Step 2: Run them to verify they fail**

Expected: FAIL because current code raises `NoKnowledgeMatchedError`.

**Step 3: Write the minimal implementation**

- Update questionnaire generation to treat empty/no-match retrieval as fallback mode.
- Build context from the brief and user input when no snippets exist.
- Persist an indicator that fallback mode was used.
- Surface a Chinese notice in the questionnaire page:
  - no relevant match
  - or no knowledge exists at all

Keep the output contract stable: a draft still saves as a questionnaire version.

**Step 4: Run the tests again**

Expected: PASS

**Step 5: Run the full suite**

**Step 6: Commit**

```bash
git add src/game_survey_workbench/services/questionnaires.py src/game_survey_workbench/routes/questionnaires.py src/game_survey_workbench/templates/questionnaires/detail.html tests/test_stage5b_questionnaire_page.py tests/test_1_0_shared_knowledge.py
git commit -m "fix(1.0): allow questionnaire drafting without matched knowledge"
```

---

### Task 6: Extend Graceful No-Knowledge Handling To Insight And Report Generation

**Files:**
- Modify: `src/game_survey_workbench/services/insights.py`
- Modify: `src/game_survey_workbench/routes/insights.py`
- Modify: `src/game_survey_workbench/services/reporting.py`
- Modify: `src/game_survey_workbench/routes/reports.py`
- Modify: `src/game_survey_workbench/templates/analysis/detail.html`
- Modify: `src/game_survey_workbench/templates/reports/detail.html`
- Test: `tests/test_stage6b_error_feedback.py`
- Test: `tests/test_1_0_shared_knowledge.py`

**Step 1: Write the failing tests**

Add tests that:

- run insight generation with no knowledge available
- verify success plus a Chinese fallback notice instead of a blocking error
- generate a report from deterministic findings/insight narrative without matched knowledge
- verify success plus a visible fallback notice

**Step 2: Run them to verify they fail**

Expected: FAIL because these flows still treat no-knowledge as blocking or opaque.

**Step 3: Write the minimal implementation**

- Apply the same fallback principle as questionnaire generation.
- Preserve explicit user messaging in the page-level workflow state.
- Do not change deterministic analysis or report structure contracts beyond adding visible notices.

If scope becomes tight, keep text coding out of this task and document it as a follow-up task in the same branch before claiming completion.

**Step 4: Run the tests again**

Expected: PASS

**Step 5: Run the full suite**

**Step 6: Commit**

```bash
git add src/game_survey_workbench/services/insights.py src/game_survey_workbench/routes/insights.py src/game_survey_workbench/services/reporting.py src/game_survey_workbench/routes/reports.py src/game_survey_workbench/templates/analysis/detail.html src/game_survey_workbench/templates/reports/detail.html tests/test_stage6b_error_feedback.py tests/test_1_0_shared_knowledge.py
git commit -m "fix(1.0): degrade insight and report generation without knowledge matches"
```

---

### Task 7: Decide And Implement Text Coding Fallback

**Files:**
- Modify: `src/game_survey_workbench/services/text_coding.py`
- Modify: `src/game_survey_workbench/routes/text_coding.py`
- Modify: `src/game_survey_workbench/templates/analysis/detail.html`
- Test: `tests/test_validation_ready_llm_fallback.py`
- Test: `tests/test_1_0_shared_knowledge.py`

**Step 1: Write the failing tests**

Add tests that clarify the accepted 1.0 behavior:

- no knowledge available
- text coding form does not crash
- either:
  - coding completes in fallback mode, or
  - the page returns a clear Chinese warning and remains operable

Pick one behavior and lock it in.

**Step 2: Run them to verify they fail**

**Step 3: Write the minimal implementation**

Preferred:

- allow basic coding without knowledge matches

Acceptable 1.0 fallback if needed:

- non-blocking warning with a retry path and no 500

**Step 4: Run the tests again**

**Step 5: Run the full suite**

**Step 6: Commit**

```bash
git add src/game_survey_workbench/services/text_coding.py src/game_survey_workbench/routes/text_coding.py src/game_survey_workbench/templates/analysis/detail.html tests/test_validation_ready_llm_fallback.py tests/test_1_0_shared_knowledge.py
git commit -m "fix(1.0): harden text coding when knowledge is unavailable"
```

---

### Task 8: Final Regression And Acceptance Check

**Files:**
- Modify: `README.md` only if workflow wording needs clarification after implementation

**Step 1: Run the full test suite**

```bash
$env:PYTHONPATH='src'; python -m pytest --tb=short -q
```

Expected: all tests passing with the new shared-knowledge coverage included.

**Step 2: Run compile verification**

```bash
$env:PYTHONPATH='src'; python -m compileall src
```

Expected: no syntax errors.

**Step 3: Manually verify the browser flow**

Check:

- homepage shows `共享知识库`
- `/knowledge` lists documents
- upload with Chinese purpose labels works without front matter
- questionnaire generation works with:
  - matching knowledge
  - no matching knowledge
  - no knowledge at all
- project page copy consistently describes shared knowledge

**Step 4: Commit any final doc or wording fixes**

```bash
git add README.md
git commit -m "docs: clarify shared knowledge workflow"  # only if needed
```

---

## Dependency Notes

- Task 1 should happen first because it establishes the homepage-first entry.
- Task 2 depends on Task 1 if the homepage links to `/knowledge`.
- Task 3 depends on Task 2 because the upload UX is centered on the shared knowledge page.
- Task 4 can happen after Tasks 1-3.
- Task 5 is the highest-priority functional fallback task.
- Task 6 depends on the chosen fallback messaging pattern from Task 5.
- Task 7 is lowest priority and may be split if execution risk grows.

## Risk Controls

- Keep the shared knowledge page intentionally simple; do not add deletion/search in 1.0.
- Avoid changing retrieval architecture; only adjust metadata injection and no-match behavior.
- Preserve current storage layout under `workspace/knowledge`.
- Prefer page-level Chinese notices over new persistence models unless absolutely necessary.

## Definition Of Done

- The user can understand that knowledge is shared across projects.
- The user can see existing knowledge documents from the homepage and `/knowledge`.
- The user can upload a document without front matter and make it usable via Chinese purpose labels.
- Questionnaire generation no longer blocks on missing or non-matching knowledge.
- The selected additional workflows no longer hard-fail on no-knowledge conditions.
- Full regression suite passes.
