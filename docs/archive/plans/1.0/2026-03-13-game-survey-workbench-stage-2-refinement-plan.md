# Game Survey Workbench Stage 2 Refinement Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the final Stage 2 credibility gap identified by the closeout assessment, so the product can be judged on real researcher usefulness rather than on scripted acceptance plumbing alone.

**Architecture:** Keep the existing local monolith, retrieval layer, provider adapter, and closeout harness. This refinement pass should add only the minimum runtime-backed assessment support and output-quality improvements needed to decide whether Stage 2 is truly complete.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, pytest, Markdown docs, existing local scripts and prompt files

---

## Relationship to Existing Plans

This plan follows:

- `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`
- `docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-assessment-plan.md`
- `docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-report.md`

It exists because the closeout report concluded:

- the Stage 2 loop is structurally working end to end
- coding persistence and evidence plumbing are no longer the active blocker
- Stage 2 is still not proven credible enough for regular researcher use with a real provider-backed runtime

This plan does **not** reopen north-star direction and does **not** start Stage 3.

## Why One More Stage 2 Pass Is Needed

The closeout assessment showed three weak points that still affect product credibility:

1. questionnaire drafts are grounded but still thin for actual researcher use
2. insight/report outputs are structurally correct but read mechanically
3. the current acceptance harness proves scripted repeatability, not real provider-backed usefulness

The refinement pass should target only those gaps.

## Success Criteria

This refinement pass is complete when:

- the closeout workflow can run in a real provider-backed mode with explicit artifact capture and clear failure reporting
- questionnaire outputs are visibly more useful than the current minimal grounded draft
- report-level insight output is less mechanical while preserving deterministic evidence structure
- the updated closeout assessment can make an evidence-backed go/no-go call on Stage 2 completion

## Non-Goals

- no Stage 3 Research Brief or Task Plan work
- no north-star changes
- no broad retrieval redesign unless a verified blocker emerges from the provider-backed run
- no dashboard-first reporting redesign
- no new collaboration or cloud features

---

## Task 1: Add runtime-backed closeout assessment mode and artifact capture

**Files:**
- Modify: `scripts/run_stage2_closeout_assessment.py`
- Modify: `tests/test_stage2_closeout_assessment.py`
- Create if needed: `docs/plans/2026-03-13-game-survey-workbench-stage-2-runtime-assessment-notes.md`

**Intent:**

- keep the current deterministic scripted mode for regression safety
- add a second mode that uses the configured runtime client when credentials are present
- capture whether the run used scripted or provider-backed output
- save or print enough artifact paths and mode metadata for manual review

**Constraints:**

- do not make automated tests depend on live credentials
- do not silently downgrade a requested provider-backed run into scripted mode

## Task 2: Tighten questionnaire output usefulness without broadening scope

**Files:**
- Modify: `src/game_survey_workbench/llm/prompts/questionnaire_design.md`
- Modify: `src/game_survey_workbench/services/questionnaires.py`
- Modify: `tests/test_questionnaire_service.py`
- Modify if needed: `tests/test_end_to_end_smoke.py`

**Intent:**

- keep the visible `## Knowledge Basis` grounding
- strengthen the draft so it better reflects segmentation, diagnostic framing, and clearer question rationale
- improve output usefulness using prompt/service shaping, not a new product surface

**Constraints:**

- do not start building a Stage 3 project-brief experience
- do not replace Markdown as the saved artifact

## Task 3: Improve insight/report wording quality while preserving evidence contracts

**Files:**
- Modify: `src/game_survey_workbench/llm/prompts/insight_synthesis.md`
- Modify: `src/game_survey_workbench/services/reporting.py`
- Modify: `tests/test_insights_service.py`
- Modify: `tests/test_reporting.py`

**Intent:**

- keep narrative and evidence section separate
- improve report readability so the executive summary and key findings feel less mechanical
- keep exactly one report-level `## Evidence Basis` section

**Constraints:**

- no redesign into a dashboard or BI-style output
- no regression in the saved evidence flow

## Task 4: Re-run closeout with real-provider evidence and update the decision docs

**Files:**
- Modify: `docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-scorecard.md`
- Modify: `docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-report.md`
- Modify if Stage 2 is complete enough: `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`
- Create if still blocked: follow-up refinement notes only if another blocker is discovered

**Intent:**

- rerun the closeout with the updated outputs
- inspect the real-provider artifacts when credentials are available
- separate real blockers from residual polish again
- only then decide whether Stage 2 can finally close

**Constraints:**

- do not update the north-star plan unless the evidence now supports Stage 2 closeout
- do not create Stage 3 planning docs unless Stage 2 is explicitly cleared

---

## Verification Checklist Before Any Completion Claim

- Run: `.venv/Scripts/python.exe -m pytest -v`
- Run: `.venv/Scripts/python.exe -m compileall src`
- Run: `.venv/Scripts/python.exe scripts/run_stage2_closeout_assessment.py`
- When credentials are available, run the provider-backed closeout mode and capture the generated artifacts
- Manually confirm:
  - questionnaire output remains visibly grounded and is more useful than the current baseline
  - insight/report wording improves without losing deterministic evidence structure
  - the closeout recommendation is supported by fresh written evidence, not inference alone

## Notes

- This refinement pass should stay as small as possible.
- The blocker is product credibility, not plumbing correctness.
- If the provider-backed run reveals a deeper retrieval or prompt issue, document that specific issue before broadening scope.
