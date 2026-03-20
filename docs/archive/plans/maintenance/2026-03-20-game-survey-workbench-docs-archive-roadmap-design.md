# Game Survey Workbench Docs Archive And Roadmap Restructure Design

## Goal

Reorganize the planning documents so that `docs/plans/` becomes the home for active future planning only, while all completed `1.0` and `2.0` planning artifacts move into versioned archive folders. At the same time, replace the old `2.0` north-star document as the primary entry point with a long-lived roadmap file that starts the next iteration sequence at `2.1`.

## Decisions

### 1. Archive structure

- `docs/plans/` will hold only currently active planning documents.
- `docs/archive/plans/1.0/` will store all `1.0` and pre-`2.0` execution history.
- `docs/archive/plans/2.0/` will store all completed `2.0` planning and implementation documents.

### 2. Main planning entry point

- Add `docs/product-roadmap.md` as the single long-lived roadmap file.
- It will state that:
  - `1.0` is complete and archived
  - `2.0` is complete and archived
  - future planning resumes at `2.1`, then `2.2`, `2.3`, and so on

### 3. Handling unfinished 2.0 ideas

- Any `2.0` directions that were never implemented will be removed from the primary roadmap narrative.
- Their existence will only remain as historical context inside the archived `2.0` documents.
- Future work will not continue under `2.0G/H/I/J/K`; it will be replanned under `2.1+`.

### 4. Treatment of currently untracked 2.0 docs

- The local but untracked `2.0C`, `2.0D`, and `2.0E` plan files should be brought into version control and archived.
- This keeps the history chain complete and avoids a gap between completed work and stored planning artifacts.

### 5. docs/plans index

- Add a small `docs/plans/README.md` that explains the directory contract:
  - active plans only
  - archive is under `docs/archive/plans/`
  - future stages should use `2.1+`

## Expected Result

After the restructure:

- `docs/plans/` is clean and future-facing
- `docs/archive/plans/` contains the complete `1.0` and `2.0` planning history
- `docs/product-roadmap.md` becomes the stable planning entry point for maintenance and future releases
- no stray temporary planning files remain outside the archive structure
