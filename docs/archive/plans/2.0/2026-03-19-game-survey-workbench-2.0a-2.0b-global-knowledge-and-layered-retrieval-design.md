# Game Survey Workbench 2.0A/2.0B Global Knowledge And Layered Retrieval Design

**Date:** 2026-03-19

**Status:** Approved for implementation

## Relationship to Existing Plans

This design follows:

- `docs/plans/2026-03-15-game-survey-workbench-2.0-north-star.md`
- `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`

It replaces the earlier assumption that the next work should continue from the 2026-03-13 Stage 2 plans. Those plans are now treated as completed 1.0 implementation history, not as pending 2.0 work.

## Goal

Ship the first 2.0 iteration by combining:

- `2.0A` Global Knowledge Library
- `2.0B` Layered Retrieval Strategy

The product should move from "shared storage with project-scoped UI framing" to "explicit global knowledge management plus project-level document selection," and retrieval should move from a single mixed pool to a task-aware dual-pool strategy.

## Product Decisions Confirmed

The following decisions were explicitly approved during brainstorming:

1. `2.0A` and `2.0B` will be delivered together in one implementation wave.
2. Project-to-knowledge linkage will use **explicit selected documents** as the primary relationship.
3. The first delivery target is the **standard launch scope**, not the minimal or maximal scope.

That means this iteration includes:

- a real global knowledge management page
- project-level knowledge selection
- dual-pool retrieval inside the selected project knowledge set
- basic retrieval-hit visibility in questionnaire and insight flows

It does not include:

- usage analytics dashboards
- query expansion dictionaries
- embedding retrieval upgrades
- advanced knowledge operations or recommendation systems

## Problem Statement

The current system already stores knowledge globally in `workspace/knowledge/`, but the UI still invites the user to upload from the project page as if knowledge were project-private.

At the same time, the retrieval layer currently treats all eligible chunks as a single pool. This creates a quality problem:

- method documents should be brought into context because they match the task stage
- domain documents should be brought into context because they match the project query

If both kinds of knowledge compete in the same lexical ranking, method documents are under-selected even when they are essential for questionnaire design or analysis interpretation.

## Scope

### In Scope

- upgrade `/knowledge` into the primary global knowledge management entry point
- add project-level selected-document persistence
- let each project choose which global knowledge documents it uses
- constrain retrieval to the project's selected documents
- add dual-pool retrieval:
  - Pool A: method/task-stage pool
  - Pool B: domain/query-matching pool
- preserve metadata-driven filtering via existing document fields
- expose basic retrieval-hit feedback in questionnaire and insight screens

### Out of Scope

- document usage analytics or hit-rate dashboards
- automated query expansion
- embedding-based semantic retrieval
- non-Markdown knowledge ingestion expansion
- report-wide knowledge analytics UI
- redesigning the workbench shell beyond what 2.0A/2.0B needs

## Chosen Approach

The selected approach is:

`global knowledge management -> explicit project document selection -> selected-set dual-pool retrieval -> basic hit feedback`

This was chosen over both:

- keeping rule-based selection as the main project mechanism
- building a much larger knowledge-operations system in the same pass

The explicit-selection model is the smallest durable structure that supports:

- correct project knowledge semantics
- inspectable retrieval behavior
- stable hit feedback
- future usage statistics without another data-model reset

## Architecture Direction

### 1. Global Knowledge Library

`/knowledge` becomes the primary home for:

- uploading knowledge
- browsing all ingested documents
- filtering by title, tags, stage, and type
- inspecting metadata already persisted on `KnowledgeDocument`

The page should be clearly global in language and interaction. It should not imply project-private storage.

### 2. Project Knowledge Selection

Project pages should stop behaving like knowledge-upload destinations.

Instead, each project should show:

- which global documents are currently selected for that project
- a selection interface for adding or removing documents from the project
- a link back to the global knowledge page for management

The primary relationship is explicit document selection, not `knowledge_pack` rules.

### 3. Selected-Set Retrieval

All project retrieval should first narrow to the set of knowledge documents selected for that project.

After that narrowing step, retrieval should run inside the selected set only.

This keeps project behavior understandable:

- if a document was not selected for the project, it should not influence the output
- if it was selected, it is eligible to be surfaced depending on retrieval pool logic

### 4. Dual-Pool Retrieval

Retrieval should be split into two internal pools.

#### Pool A: Method Pool

Method documents should be included because they are relevant to the current task stage, not because they win TF-IDF competition.

Entry rules:

- document stage matches the requested task stage
- or document priority is high enough to force inclusion

Typical document types here are:

- `guide`
- `theory`
- `method`

Pool A should be small and bounded, for example top 3 after deterministic ordering.

#### Pool B: Domain Pool

Domain documents should be ranked using the current lexical retrieval logic, but only within the selected project set.

Typical document types here are:

- `experience`
- `research`
- `benchmark`

Pool B should use the user/task query and remain bounded, for example top 5.

#### Final Result

Final retrieval context should be:

- Pool A results
- plus Pool B results
- deduplicated by source document and snippet content

Each returned item should carry enough metadata to explain:

- which document it came from
- which pool selected it
- which snippet text was injected

## Data Model Changes

### New Project Selection Table

Add a new persistence model such as `ProjectKnowledgeSelection`.

Suggested fields:

- `id`
- `project_slug`
- `knowledge_document_id`
- `selected_at`

This table is the canonical project-to-knowledge relationship for 2.0.

### Existing Models

`KnowledgeDocument` remains the source of truth for:

- title
- source path
- doc type
- stages
- tags
- scenario
- priority

`ProjectRecord.knowledge_pack` should remain temporarily for compatibility, but it should no longer be the main retrieval driver for the 2.0 path.

## Retrieval Contracts

The retrieval layer should gain explicit support for:

- filtering by selected document ids
- splitting candidates into method and domain pools
- returning pool metadata in results

The existing TF-IDF ranking can remain for Pool B in this iteration.

No embedding or query-expansion logic is needed in this design.

## UI And Interaction Design

### Knowledge Page

The global knowledge page should support:

- upload
- list
- filter
- metadata visibility

It should read as a management page, not just a passive listing page.

### Project Page

The project page should support:

- viewing selected knowledge
- editing selection from the global knowledge set
- understanding that project outputs use the selected set

The project page should no longer present a project-local upload form as the primary interaction.

### Questionnaire And Insight Pages

The generated output views should show a simple "knowledge basis" block that explains:

- which documents were used
- which pool each item came from
- which snippets were injected

This is basic hit feedback, not a statistics dashboard.

## Error Handling

The behavior should stay explicit:

- if a project has no selected knowledge, generation should fail clearly and tell the user to select knowledge first
- if Pool A is empty but Pool B has hits, continue
- if Pool B is empty but Pool A has hits, continue
- if both pools are empty, fail clearly
- do not silently widen retrieval back to the entire workspace

## Backward Compatibility

This iteration should preserve runtime stability without preserving old semantics indefinitely.

Compatibility rules:

- keep old fields in place unless removal is required
- migrate old UI tests and behavior away from project-upload-first language
- do not silently fallback from "no selected knowledge" to global retrieval

That last point is important because silent fallback would reintroduce the same product ambiguity 2.0A is meant to fix.

## Testing Strategy

The implementation should prove four things:

1. project/document selection persists correctly
2. retrieval only uses selected project knowledge
3. dual-pool retrieval behaves deterministically
4. questionnaire and insight flows surface basic hit feedback

Tests should cover:

- service-level selection persistence
- route-level selection updates
- knowledge-page filtering
- retrieval behavior with mixed method/domain fixtures
- UI rendering of selected knowledge and retrieval-hit metadata
- explicit failure when project selection is empty

## Expected Outcome

After 2.0A/2.0B:

- users will understand that knowledge is global
- projects will explicitly declare which knowledge they use
- retrieval quality will improve because method and domain knowledge are no longer forced into one mixed competition
- questionnaire and insight outputs will become easier to trust because the system will show which knowledge it actually used

This establishes the correct foundation for later 2.0 work such as richer feedback, query expansion, and knowledge usage analytics.
