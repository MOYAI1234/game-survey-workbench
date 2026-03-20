# Game Survey Workbench Stage 2C Questionnaire Grounding Design

**Date:** 2026-03-13

**Status:** Approved for implementation

## Relationship to Existing Plans

This design follows:

- `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`
- `docs/plans/2026-03-13-game-survey-workbench-stage-2-llm-knowledge-plan.md`

It does not change the north-star direction. It is the next design artifact after Stage 2A and Stage 2B foundations were completed.

## Goal

Make questionnaire drafting the first truly knowledge-guided workflow in the workbench.

The user should be able to submit a research goal and optional hypotheses for a project, and receive:

- an editable Markdown questionnaire draft
- a visible `## Knowledge Basis` section in that Markdown
- structured citations/snippets saved alongside the draft for later reuse

## Why This Comes Next

Stage 2A and 2B already established the foundations needed for grounded drafting:

- metadata-aware local retrieval
- project-aware knowledge filtering
- real provider-backed LLM execution
- explicit failure behavior when LLM configuration is missing

What is still missing is the first user-facing workflow that actually combines those pieces into product value.

Questionnaire drafting is the correct next step because it sits at the front of the permanent core loop:

`Knowledge Base -> Questionnaire Design -> Data Analysis -> Markdown Report`

## Scope

In scope for Stage 2C:

- retrieve project-filtered knowledge for questionnaire design tasks
- assemble a grounded questionnaire prompt from project context plus retrieval results
- run the configured LLM client to generate an editable Markdown questionnaire draft
- append a visible knowledge-basis section into the saved Markdown output
- persist structured citations/snippets with the saved draft
- fail clearly when project, knowledge, or LLM runtime prerequisites are missing

Out of scope for Stage 2C:

- open-text coding
- insight synthesis from statistical findings
- research brief UI
- multi-turn questionnaire editing UI
- embedding or hybrid retrieval upgrades

## Chosen Approach

The selected approach is:

`retrieve knowledge -> assemble grounded context -> generate Markdown draft -> save Markdown plus structured citations`

This was chosen over a structured questionnaire DSL because the immediate product need is an editable draft that a researcher can review and modify directly. Markdown remains the final editable artifact, while structured citation persistence keeps the system ready for Stage 2D reuse.

## Retrieval Strategy

Stage 2C will continue to use the current deterministic retrieval approach instead of introducing embeddings in the same step.

The retrieval flow is:

1. use the project's `knowledge_pack` to restrict `doc_types` and `scenarios`
2. use questionnaire-design task context to pass `stages=["design"]`
3. score matching chunks lexically against the design request
4. sort results deterministically using score and priority
5. pass the top matched snippets into prompt assembly

This keeps the behavior inspectable and testable while the first grounded questionnaire workflow is established.

## Architecture

### Service Flow

`routes/questionnaires.py` should stop depending on user-supplied knowledge snippets as the primary source of grounding.

Instead, the service flow should become:

1. load project from `project_slug`
2. retrieve project-filtered knowledge for questionnaire design
3. load the questionnaire prompt template
4. build the configured LLM client
5. generate a Markdown draft
6. append a `## Knowledge Basis` section from the retrieved evidence
7. persist the draft plus structured citations/snippets

### Data Shape

`QuestionnaireDraftRequest` should continue to accept:

- `research_goal`
- `hypotheses`

Optional manual `knowledge_snippets` may remain temporarily for compatibility, but Stage 2C should no longer rely on them as the primary grounding path.

`QuestionnaireSpecVersion` should gain structured grounding fields such as:

- `citations`
- `retrieved_snippets`

Those fields should store enough information to support later inspection and reuse, such as document title, chunk text, tags, scenario, and doc type.

### Prompt Contract

The questionnaire prompt should explicitly require:

- Markdown output
- clear section structure
- questionnaire questions grouped in an editable way
- the draft to stay grounded in supplied evidence
- no fabricated citations

The saved Markdown should include a visible evidence section so human reviewers can inspect why certain questions were suggested.

## Error Handling

Stage 2C should fail clearly in these cases:

- project not found
- no eligible knowledge retrieved for the design request
- LLM runtime not configured
- LLM provider returns an unusable response

Clear failure is preferred over silently generating generic questionnaire text.

## Testing Strategy

Automated tests should prove behavior, not just string inclusion.

Stage 2C tests should cover:

- project-aware retrieval is used during questionnaire drafting
- grounded snippets are passed into prompt/context assembly
- generated Markdown is saved to disk and database
- structured citations/snippets are persisted with the draft
- missing project, missing knowledge, and missing LLM configuration fail clearly

Manual acceptance should use at least these two real scenarios:

1. `研究回归玩家的回归理由`
2. `研究付费玩家对于当前版本的满意度`

Acceptance should focus on:

- whether the questionnaire is genuinely editable
- whether question structure matches the research goal
- whether the knowledge-basis section contains useful, inspectable evidence

## Expected Outcome

After Stage 2C, the product should have its first credible knowledge-guided drafting workflow:

- the researcher provides a design objective
- the system retrieves relevant local knowledge
- the LLM produces a grounded questionnaire draft
- the workbench preserves both the editable Markdown and the supporting evidence

Stage 2D can then build on the same retrieval and evidence patterns for open-text coding and insight synthesis.
