# Game Survey Workbench 1.0 Knowledge Closeout Design

**Date:** 2026-03-15

**Status:** Approved for 1.0 closeout planning

## Why This Is A 1.0 Blocker

The current product stores knowledge at the workspace level but presents knowledge upload inside each project page. That mismatch breaks user understanding at exactly the point where the knowledge-guided workflow is supposed to feel trustworthy.

In real validation, this causes three 1.0 acceptance failures:

1. Users believe knowledge is project-private even though it is actually shared across projects.
2. Users cannot see what knowledge exists globally or whether upload succeeded in a usable way.
3. Questionnaire generation can hard-fail with `No knowledge matched this questionnaire request.` even when the user has already uploaded a document, because the system expects internal metadata that the UI never helped the user supply.

This is not a 2.0 optimization. It is a core-loop usability blocker inside `Knowledge Base -> Questionnaire Design -> Data Analysis -> Markdown Report`.

## Current State

### What the product does today

- Knowledge upload lives on the project detail page.
- Uploaded files are written into `workspace/knowledge`.
- Knowledge retrieval is already workspace-level, not project-private.
- Projects currently only carry `knowledge_pack` filters such as `doc_types` and `scenarios`.
- Questionnaire generation requires `stage=["design"]` knowledge matches.
- Users are effectively expected to author Markdown front matter if they want the system to classify knowledge correctly.

### What feels broken to users

- The UI implies “upload knowledge for this project.”
- The product does not expose a visible shared knowledge library.
- Upload success does not establish what the document is for.
- Missing metadata leads to hidden retrieval misses.
- No-match behavior is a hard stop instead of a quality downgrade.

## 1.0 Goals

The 1.0 closeout should make knowledge use understandable and usable without changing the product’s core architecture.

### Required outcomes

- Knowledge is presented as a shared workspace asset, not a project-private asset.
- The homepage becomes the primary entry point for knowledge management.
- Users can see which knowledge documents currently exist.
- Users can upload knowledge without writing front matter.
- Upload supports Chinese purpose labels and multi-select purpose assignment.
- The system auto-populates internal metadata from those purpose choices.
- Primary workflows do not hard-fail just because no knowledge matched.
- The UI clearly distinguishes “knowledge-enhanced” from “fallback/basic” generation.

## Non-Goals

These remain out of scope for this 1.0 closeout:

- document deletion
- project-specific document enable/disable selection
- semantic retrieval overhaul
- auto-tagging or auto-classification
- batch import/export management
- knowledge search/filter UI beyond a minimal list
- retrieval relevance visualization

## Approved Product Shape

## 1. Homepage-First Shared Knowledge Entry

The homepage should expose a first-class `共享知识库` entry in the top navigation and in the main page content.

The homepage should show a compact summary block:

- total knowledge document count
- the most recent 3-5 documents
- a button or link to the shared knowledge page

This creates the correct mental model before the user even enters a project.

## 2. Lightweight Shared Knowledge Page

1.0 should add a minimal shared knowledge page rather than keeping knowledge management hidden inside projects.

This page should support:

- listing current knowledge documents
- showing each document’s title
- showing each document’s purpose labels
- showing source filename or upload time if available
- uploading a new document
- showing upload success/failure feedback

This page is intentionally lightweight. It is not a full management console.

## 3. Project Page Reframing

Project pages should stop implying ownership of knowledge.

The project detail page should:

- rename the section from project-specific upload language to shared knowledge language
- explain that the current project retrieves from the shared knowledge library
- link to the shared knowledge page
- optionally show a compact summary like “currently shared knowledge documents: N”

The project page can keep a shortcut upload form for convenience, but that form must explicitly say it uploads into the shared library.

## Upload Design

## 4. Purpose-Based Upload Instead of Manual Front Matter

Users should not be required to author Markdown metadata in order to make knowledge usable.

The upload form should support purpose multi-select with these options:

- `问卷设计`
- `问卷分析`
- `报告写作`

The backend should map those selections to internal metadata.

### Initial mapping

- `问卷设计` -> `stage=["design"]`
- `问卷分析` -> `stage=["analysis"]`
- `报告写作` -> `stage=["report"]`

Additional internal defaults can remain simple in 1.0:

- `doc_type="guide"` unless front matter already provides a more specific value
- keep `tags=[]` by default
- keep `scenario=None` unless already provided

### Priority of metadata sources

For 1.0, explicit UI selections should take precedence over absent or ambiguous front matter because the goal is to reduce user confusion.

Recommended precedence:

1. upload form purpose selections
2. existing front matter if provided
3. fallback defaults

### Title fallback

If no title metadata exists:

1. use front matter title if present
2. else use first Markdown `# Heading`
3. else use filename stem

## Fallback Behavior When Knowledge Is Missing

## 5. No-Match Should Degrade, Not Crash

Knowledge should improve quality, not function as a strict gate that blocks first-time use.

The product should distinguish two modes:

- `knowledge-enhanced`: one or more relevant knowledge snippets matched
- `basic/fallback`: no relevant knowledge matched, generation continues without retrieval grounding

### Standard user-facing message

When no relevant knowledge matched:

`当前未匹配到相关知识，已仅基于研究简报和输入生成基础版本。建议补充共享知识库以提升质量。`

When the shared knowledge library is empty:

`当前还没有知识文档，已先生成基础版本。建议补充共享知识库以提升问卷、洞察和报告质量。`

## 6. Workflow Coverage in 1.0

### Must cover in 1.0

- Questionnaire design

This is the earliest and most user-visible LLM workflow. It must not hard-fail on first use.

### Strongly recommended in 1.0

- Insight generation
- Report generation

These workflows already have enough deterministic context to produce a basic result without knowledge grounding.

### Lowest-priority fallback in 1.0

- Text coding

Text coding can still operate in a basic LLM mode without knowledge, but if implementation scope becomes tight, 1.0 can settle for “no crash + clear warning” first, then unify behavior later.

## UX and Messaging Rules

## 7. Chinese-First UI

All fixed user-facing wording for the shared knowledge flow should be Chinese:

- section labels
- upload labels
- purpose labels
- success/failure alerts
- empty states
- fallback notices

Markdown knowledge content and downstream questionnaire/report output may remain language-flexible, but the app shell should stay Chinese-first.

## 8. Explicit Outcome Feedback

The product should make these states visible:

- upload succeeded
- upload failed
- document currently exists in shared knowledge
- current workflow used shared knowledge
- current workflow fell back without shared knowledge

Users should never have to infer whether knowledge was uploaded or used.

## 1.0 vs 2.0 Boundary

### 1.0 closeout scope

- homepage entry for shared knowledge
- lightweight shared knowledge page
- purpose-based upload with multi-select
- auto-generated metadata from UI selections
- project-page reframing to shared-library language
- graceful fallback when no knowledge matched
- visible Chinese feedback for upload and fallback states

### 2.0 enhancements

- document deletion and archive controls
- project-specific selection of enabled documents
- search/filtering by tags and purpose
- similarity-based retrieval upgrades
- match previews and citation relevance scores
- historical project recommendation and auto-reuse

## Acceptance Criteria

1. A first-time user can upload a Markdown document without writing front matter.
2. That user can label the document as `问卷设计` and then successfully generate a questionnaire draft.
3. The homepage clearly communicates that knowledge is shared across projects.
4. The shared knowledge page shows existing documents and their purpose labels.
5. A project page no longer implies project-private knowledge ownership.
6. If no relevant knowledge matches, questionnaire generation still returns a usable draft and shows a Chinese fallback message.
7. The same fallback principle applies to the other selected workflows in scope.

## Recommended Follow-Up Artifact

The next artifact should be a task-by-task implementation plan that preserves these constraints:

- minimal architecture change
- no new dependencies
- route/template-first work
- only the smallest necessary service-layer changes for metadata injection and no-match fallback
