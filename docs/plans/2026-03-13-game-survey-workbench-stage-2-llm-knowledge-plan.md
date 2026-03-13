# Game Survey Workbench Stage 2: LLM + Knowledge Integration Plan

**Date:** 2026-03-13

**Status:** Planned

## Relationship to the North Star Plan

This document is the first stage plan derived from:

- `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`

Its purpose is to move the product through Stage 2 without changing the long-term direction.

## Stage Goal

Make the knowledge base and LLM layer genuinely useful in the MVP, so the product becomes a credible knowledge-guided research workbench rather than a collection of local utilities with prompt placeholders.

## Why This Stage Comes Next

The product already has:

- local workbench shell
- project persistence
- survey upload and normalized schema
- deterministic report path

The largest gap is the product’s promised differentiator:

- knowledge-guided questionnaire help
- knowledge-guided interpretation
- LLM-assisted open-text synthesis

Without this stage, the product structure exists but the core “research amplification” value is still weak.

## Stage Outcomes

At the end of this stage, the product should be able to:

1. ingest knowledge documents with richer metadata and persistent retrieval-ready structure
2. retrieve relevant knowledge by task type and project context
3. run a real LLM client through a stable provider adapter
4. generate questionnaire drafts grounded in retrieved knowledge
5. generate open-text coding and insight summaries grounded in retrieved knowledge and deterministic inputs
6. expose source evidence clearly enough that outputs are inspectable rather than magical

## In Scope

- retrieval quality and metadata filtering
- provider-agnostic LLM runtime integration
- prompt execution plumbing
- questionnaire context assembly
- open-text coding workflow
- insight synthesis workflow
- explicit source/citation handling in LLM-supported outputs
- tests that prove knowledge is actually injected into contexts

## Out of Scope

- Research Brief and Task Plan UI
- major project-homepage redesign
- advanced matrix/ranking analytics
- multi-user collaboration
- cloud deployment
- replacing the current workbench shell

## Recommended Sub-Stages

### Stage 2A: Retrieval Foundation Hardening

Focus:

- document metadata completeness
- chunking quality
- retrieval API improvements
- project-aware filtering

Deliverables:

- stronger knowledge metadata model
- retrieval service with scenario/stage/doc-type filtering
- deterministic tests for retrieval relevance inputs

### Stage 2B: Real LLM Runtime Integration

Focus:

- provider abstraction that can run against a real model
- configuration model for local use
- fake/test client retained for automated tests

Deliverables:

- LLM configuration settings
- provider adapter interface
- safe fallback behavior when credentials are missing

### Stage 2C: Questionnaire Design Grounding

Focus:

- retrieve relevant knowledge for questionnaire design
- assemble grounded questionnaire prompts
- persist citations or knowledge snippets alongside drafts

Deliverables:

- improved questionnaire draft service
- visible knowledge grounding in saved outputs

### Stage 2D: Open-Text Coding and Insight Synthesis

Focus:

- route open text and “other” text through LLM-supported coding
- combine deterministic stats and retrieved knowledge into insight narratives

Deliverables:

- text coding service
- insight synthesis service
- output structures that preserve source evidence

## Architecture Direction

Stage 2 should preserve the current monolith but make the internal boundaries more explicit:

- `retrieval/` handles chunking, embedding persistence, and filtered search
- `llm/` handles provider config, adapter interface, and prompt execution
- `services/questionnaires.py` consumes retrieval + llm
- `services/insights.py` consumes deterministic findings + retrieval + llm
- `services/reporting.py` should remain downstream, consuming saved outputs instead of re-deriving logic ad hoc

## Product Rules for This Stage

- Knowledge retrieval must be explicit, inspectable, and task-specific.
- LLM outputs must always be grounded in structured context.
- Deterministic inputs remain the foundation for analytical claims.
- Missing knowledge or missing LLM config should fail clearly, not silently fabricate.
- Tests must validate context assembly and fallback behavior, not only string existence.

## Success Criteria

This stage is complete when:

- questionnaire draft generation clearly uses retrieved knowledge
- open-text coding can run through the LLM adapter with a testable fake client
- insight synthesis combines stats + themes + knowledge in a traceable way
- the workbench can produce outputs that reference knowledge evidence rather than generic text

## Execution Guidance

The first implementation plan under this stage should likely begin with:

1. retrieval metadata and filtering hardening
2. LLM settings and provider adapter
3. questionnaire grounding improvements
4. open-text coding service
5. insight synthesis integration

Implementation plans under this stage should remain small and test-driven, but each should explicitly tie back to this stage plan.
