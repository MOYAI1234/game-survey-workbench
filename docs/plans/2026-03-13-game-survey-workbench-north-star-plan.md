# Game Survey Workbench North Star Plan

**Date:** 2026-03-13

**Status:** Approved baseline roadmap

## Purpose

This document is the long-lived product roadmap for the project. Its role is to keep development aligned across sessions and across agents, so future implementation plans can extend the product without re-deciding the overall direction each time.

This is not a single execution checklist. It is the stable product-level plan that defines the intended final form, the major stages on the path there, and the constraints that should not drift unless the product owner explicitly changes them.

## Product End State

The product is locked to this target shape:

- a local-first tool
- delivered as a local Web workbench
- used by an individual researcher or analyst
- focused on game survey research
- driven by a knowledge base
- centered on questionnaire design, survey analysis, and Markdown report generation

The expected user experience is:

- start the service locally
- open it in a browser
- manage projects, knowledge, questionnaires, datasets, analysis runs, and reports in one local workspace

## Core Product Loop

The permanent product loop is:

`Knowledge Base -> Questionnaire Design -> Data Analysis -> Markdown Report`

This loop is the core of the product. New features should strengthen this loop rather than compete with it.

The three visible workbench entry points remain:

- Questionnaire Design
- Data Analysis
- Report Generation

These entry points may become better connected over time, but they should remain independently usable.

## Product Positioning

The product is not a generic AI workspace and not a chat-first assistant.

It is a research workbench with:

- explicit project context
- persistent files and versions
- deterministic analytics where needed
- LLM support where interpretation, drafting, coding, or synthesis adds value

The product should help a researcher do better work, not replace the structure of research practice.

## Operating Principles

### 1. Local-first is non-negotiable

The product runs locally and stores its core state locally.

- local database
- local file workspace
- local knowledge source files
- local report artifacts

Cloud-native platform features are not part of the default direction.

### 2. Web workbench is the product shell

The main product shell is a local Web interface opened in the browser after starting the local service.

Do not redirect the roadmap toward:

- native desktop shells as the main priority
- Electron/Tauri/PySide migration as a default path
- SaaS-first architecture

### 3. Knowledge-guided research is the core differentiator

The product should not behave like a thin survey upload tool.

Knowledge must actively support:

- questionnaire drafting
- question framing
- analysis interpretation
- report explanation
- recommendation quality

### 4. Rules constrain LLM output

Deterministic logic remains responsible for:

- file handling
- import validation
- schema normalization
- statistical summaries
- run persistence
- report versioning

LLM support remains responsible for:

- drafting
- text coding
- synthesis
- interpretation
- explanation
- recommendation framing

### 5. Markdown remains the final editable output

Reports and key artifacts should continue to prioritize Markdown so a researcher can edit, reuse, and archive outputs without lock-in.

## Non-Goals

These are explicitly outside the default roadmap unless the product owner later changes direction:

- multi-user collaboration platform
- permissions and role system
- cloud SaaS delivery
- complex workflow orchestration engine
- BI/dashboard-first product shape
- chat-only research assistant that replaces the workbench structure
- native desktop app as the primary shell
- heavy external questionnaire-platform integration as a first-order priority

## Current State Assessment

As of 2026-03-13, the product has a working MVP foundation:

- local FastAPI + server-rendered UI shell
- project creation and workspace layout
- knowledge document parsing and ingestion basics
- dataset import pipeline
- strict dual-header upload contract for question typing
- persisted analysis runs
- report generation tied to analysis runs
- real-sample regression coverage

What is still incomplete at the product level is the core “knowledge + LLM” value layer:

- knowledge retrieval quality is still basic
- LLM integration exists only as scaffolding and prompt files
- questionnaire generation is not yet a fully credible knowledge-guided assistant
- text coding and insight synthesis are not yet delivering the final product promise

## Roadmap Stages

### Stage 1: MVP Flow Foundation

Goal:

- make the local workbench usable end to end

Scope:

- project creation
- knowledge ingestion basics
- questionnaire draft workflow skeleton
- survey upload and normalized import
- deterministic analysis foundation
- report generation

Status:

- mostly completed

### Stage 2: Knowledge + LLM Product Core

Goal:

- make the knowledge base and LLM layer genuinely useful, not just structurally present

Scope:

- stronger retrieval pipeline
- better metadata-aware retrieval
- provider-agnostic but real LLM execution
- questionnaire generation grounded in retrieved knowledge
- open-text coding grounded in prompts and source evidence
- insight synthesis that combines deterministic findings and retrieved knowledge
- clearer citation and evidence flow into outputs

Priority:

- highest current development priority

### Stage 3: Workbench Context Layer

Goal:

- improve project continuity and context sharing across workflows

Likely scope:

- lightweight project kickoff page
- Research Brief as project truth source
- Task Plan derived from Research Brief
- clearer project homepage and workflow guidance

Important note:

- this stage is part of the long-term product direction
- it should not displace Stage 2 while the MVP core value is still incomplete

### Stage 4: Advanced Research Capability Expansion

Goal:

- extend the workbench beyond baseline survey research support

Potential scope:

- richer question-type support
- matrix and ranking normalization improvements
- stronger cross-analysis workflows
- richer recommendation logic
- deeper knowledge feedback loops from reports and prior projects

## Priority Rules for Future Sessions

Unless the product owner explicitly changes direction, future implementation work should follow these rules:

1. Prefer work that strengthens the core loop over shell polish.
2. Prefer knowledge + LLM value creation over large UX reshaping.
3. Prefer stable contracts and deterministic foundations over broad compatibility hacks.
4. Prefer phase-aligned work over opportunistic feature additions.
5. Do not elevate Stage 3 or Stage 4 work above Stage 2 without explicit approval.

## Development Continuity Rules

For future agent sessions:

- read this north-star plan first
- then read the current stage plan
- then execute within that scope

If a new idea appears to conflict with this document:

- do not silently adapt the roadmap
- surface the conflict explicitly
- ask for confirmation before changing direction

## Immediate Next Step

The next planning artifact should be a stage-level implementation plan for:

`LLM + Knowledge Integration`

That stage plan should advance the product along Stage 2 without changing the north-star shape defined here.

## Current Stage Status

As of 2026-03-15, the roadmap status within Stage 2 is:

- Stage 2A `Retrieval Foundation Hardening`: completed
- Stage 2B `Real LLM Runtime Integration`: completed
- Stage 2C `Questionnaire Design Grounding`: completed
- Stage 2D `Open-Text Coding and Insight Synthesis`: core implementation completed on `master`
- Stage 2D follow-up `Report Evidence Hardening`: completed on `master`
- Stage 2 closeout assessment: completed on `codex/stage2-closeout-assessment`
- final Stage 2 refinement pass: completed on `codex/stage2-refinement-implementation`
- Stage 2 provider-backed closeout validation: completed on `codex/stage2-refinement-implementation`
- Stage 2 closeout recommendation: `Stage 2 complete - ready for Stage 3 planning`

This status update clarifies execution order for future sessions. The final Stage 2 refinement pass and provider-backed closeout validation have been completed. Future sessions may begin Stage 3 planning while keeping any remaining Stage 2 shell-polish items scoped as follow-up work rather than phase blockers.

## Current Product State After Stage 2D Core Implementation

The product now has these Stage 2 capabilities in place:

- richer knowledge metadata parsing with `doc_type`, `stages`, `tags`, `scenario`, and `priority`
- deterministic filtered retrieval using project knowledge-pack constraints
- project-aware retrieval helper for downstream workflows
- configurable LLM runtime settings
- provider-agnostic LLM client selection
- an OpenAI-compatible HTTP runtime adapter with explicit missing-config failure behavior
- grounded questionnaire draft generation driven by project retrieval + LLM prompt execution
- editable Markdown questionnaire output with visible `Knowledge Basis`
- structured questionnaire citation/snippet persistence for later reuse
- open-text coding prompt loading, context assembly, retrieval, and persistence through `CodingResult`
- insight synthesis prompt loading, context assembly, retrieval, and persistence through `InsightRecord`
- analysis-side routes for text coding and insight synthesis
- typed exceptions for missing project, missing knowledge, and related analysis-side failures
- persisted analysis-context loading from `analysis_run_id`
- text coding routes bound to saved free-text inputs instead of client-supplied response lists
- malformed coding output rejection through a typed format error, with no false-success persistence
- insight synthesis routes bound to saved coding results and deterministic findings reconstructed from persisted run artifacts
- saved insight narrative and saved evidence persisted as separate report concerns
- report rendering support for one clean report-level `## Evidence Basis` section
- end-to-end regression coverage for the persisted evidence flow

What remains incomplete before Stage 2 can be considered fully closed is no longer the Stage 2D evidence plumbing itself. The remaining question is overall Stage 2 readiness and credibility:

- validate questionnaire grounding, coding, insight synthesis, and reporting against more realistic research inputs beyond the current regression fixtures
- identify whether retrieval quality, prompt quality, or output usefulness still need another Stage 2 refinement pass
- decide explicitly whether Stage 2 is complete enough to begin Stage 3 context-layer planning

After the 2026-03-15 provider-backed closeout validation, that readiness question is now resolved:

- the end-to-end loop is structurally working on realistic closeout fixtures
- coding persistence and report-level evidence rendering are no longer the active blockers
- provider-backed acceptance evidence now shows grounded questionnaire output, actionable insight synthesis, and readable report output credible enough for Stage 2 completion

## Next Planned Artifact

The next concrete planning artifact should be a Stage 3 planning document focused on the workbench context layer described above.

## After Stage 2D

Now that the final Stage 2 refinement pass and provider-backed closeout validation have been completed, the next planned focus can move forward inside the north-star order:

- begin Stage 3 planning for the workbench context layer
- keep any remaining Stage 2 shell-polish work narrowly scoped and subordinate to the Stage 3 planning sequence

Future sessions should continue to respect the stage order:

`Stage 2A/2B foundations -> Stage 2C questionnaire grounding -> Stage 2D coding and insight synthesis -> Stage 2D report/evidence hardening -> Stage 2 closeout assessment -> final Stage 2 refinement pass -> provider-backed closeout validation -> Stage 3 context work`
