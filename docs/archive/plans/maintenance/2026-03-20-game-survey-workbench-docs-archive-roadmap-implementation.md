# Game Survey Workbench Docs Archive And Roadmap Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Archive completed `1.0` and `2.0` planning artifacts, introduce a new long-lived roadmap entry point, and leave `docs/plans/` as the home for future active plans only.

**Architecture:** This is a docs-only repository restructure. The work consists of creating archive directories, moving tracked planning files into versioned archive buckets, importing the local untracked `2.0C/2.0D/2.0E` plans into version control, and adding small index documents that define the new planning workflow.

**Tech Stack:** Markdown, git moves, repository documentation structure

---

### Task 1: Create archive directories and active-plan index

**Files:**
- Create: `docs/archive/plans/1.0/.gitkeep`
- Create: `docs/archive/plans/2.0/.gitkeep`
- Create: `docs/plans/README.md`

**Step 1: Write the files**

- Add archive directories so the structure exists in git.
- Add `docs/plans/README.md` explaining:
  - active plans only
  - historical plans live under `docs/archive/plans/`
  - future versioning resumes at `2.1`

**Step 2: Verify paths**

Run: `Get-ChildItem docs\\archive\\plans -Recurse`
Expected: `1.0`, `2.0`, and the new files exist.

**Step 3: Commit**

```bash
git add docs/archive/plans docs/plans/README.md
git commit -m "docs: add archive structure and active plan index"
```

### Task 2: Archive all tracked 1.0 planning history

**Files:**
- Move tracked `1.0` and pre-`2.0` files from `docs/plans/` to `docs/archive/plans/1.0/`

**Step 1: Move files**

Move the following into `docs/archive/plans/1.0/`:

- all `2026-03-12-*`
- all `2026-03-13-game-survey-workbench-stage-2*`
- `2026-03-13-game-survey-workbench-north-star-plan.md`
- `2026-03-14-game-survey-workbench-stage-2-refinement-implementation.md`
- all `2026-03-15-game-survey-workbench-1.0-*`
- all `2026-03-15-game-survey-workbench-stage-3*` through `stage-7*`
- all `2026-03-15-validation-ready-bootstrap-*`

**Step 2: Verify git sees renames**

Run: `git status --short`
Expected: primarily `R` entries for the moved files.

**Step 3: Commit**

```bash
git add -A docs/plans docs/archive/plans/1.0
git commit -m "docs: archive 1.0 planning history"
```

### Task 3: Import and archive all 2.0 planning history

**Files:**
- Move tracked `2.0` files from `docs/plans/` to `docs/archive/plans/2.0/`
- Add currently untracked:
  - `2026-03-19-game-survey-workbench-2.0c-smart-data-and-batched-coding.md`
  - `2026-03-19-game-survey-workbench-2.0d-knowledge-format-expansion.md`
  - `2026-03-19-game-survey-workbench-2.0e-output-usability.md`

**Step 1: Import local files**

Copy the three local `2.0C/2.0D/2.0E` plan docs from the main workspace into the worktree.

**Step 2: Move all 2.0 docs**

Move these into `docs/archive/plans/2.0/`:

- `2026-03-15-game-survey-workbench-2.0-north-star.md`
- `2026-03-19-game-survey-workbench-2.0a-2.0b-global-knowledge-and-layered-retrieval-design.md`
- `2026-03-19-game-survey-workbench-2.0a-2.0b-global-knowledge-and-layered-retrieval-implementation.md`
- `2026-03-19-game-survey-workbench-2.0c-smart-data-and-batched-coding.md`
- `2026-03-19-game-survey-workbench-2.0d-knowledge-format-expansion.md`
- `2026-03-19-game-survey-workbench-2.0e-output-usability.md`
- `2026-03-19-game-survey-workbench-2.0f-experience-polish.md`

**Step 3: Commit**

```bash
git add -A docs/plans docs/archive/plans/2.0
git commit -m "docs: archive completed 2.0 planning history"
```

### Task 4: Replace the old 2.0 roadmap with a durable product roadmap

**Files:**
- Create: `docs/product-roadmap.md`

**Step 1: Write the roadmap**

The roadmap must:

- mark `1.0` as complete and archived
- mark `2.0` as complete and archived
- declare `2.1` as the next planning line
- explain naming rules for `2.1`, `2.2`, `2.3`
- point readers to `docs/plans/` for active plans and `docs/archive/plans/` for history

**Step 2: Commit**

```bash
git add docs/product-roadmap.md
git commit -m "docs: add long-lived product roadmap for post-2.0 planning"
```

### Task 5: Add archive notes for dropped 2.0 leftovers

**Files:**
- Create: `docs/archive/plans/2.0/README.md`

**Step 1: Write the note**

Explain briefly that:

- `2.0` implementation has concluded
- some late `2.0` directional ideas were not implemented
- they are intentionally not carried forward under `2.0`
- future work must be replanned under `2.1+`

**Step 2: Commit**

```bash
git add docs/archive/plans/2.0/README.md
git commit -m "docs: record archived 2.0 completion and dropped follow-on directions"
```

### Task 6: Final cleanup verification

**Files:**
- No content changes required unless cleanup notes need adjustment

**Step 1: Verify final docs layout**

Run:

- `Get-ChildItem docs\\plans`
- `Get-ChildItem docs\\archive\\plans\\1.0`
- `Get-ChildItem docs\\archive\\plans\\2.0`
- `git status --short`

Expected:

- `docs/plans/` contains only active/future-facing planning entry files
- `1.0` and `2.0` history sits under archive
- no stray untracked plan files remain in the main planning directory

**Step 2: Commit if needed**

If any final cleanup changes were needed:

```bash
git add -A
git commit -m "docs: finalize planning archive cleanup"
```
