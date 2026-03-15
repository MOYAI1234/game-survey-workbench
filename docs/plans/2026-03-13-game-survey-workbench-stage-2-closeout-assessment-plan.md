# Game Survey Workbench Stage 2 Closeout Assessment Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Determine whether Stage 2 is credible enough for regular researcher use by running realistic acceptance loops across the full `Knowledge Base -> Questionnaire Design -> Data Analysis -> Markdown Report` workflow.

**Architecture:** Reuse the current local monolith, existing regression fixtures, `scripts/seed_demo_workspace.py`, and `scripts/verify_local_http.py` as the assessment foundation. Add only the minimum acceptance harness, fixture manifest, and result-reporting artifacts needed to judge Stage 2 readiness without changing north-star direction or starting Stage 3 work.

**Tech Stack:** Python 3.12, FastAPI, pytest, httpx, uvicorn, Markdown docs, existing local workspace scripts

---

## Relationship to Current Plans

This plan follows:

- `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`
- `docs/plans/2026-03-13-game-survey-workbench-stage-2-llm-knowledge-plan.md`
- `docs/plans/2026-03-13-game-survey-workbench-stage-2d-report-evidence-hardening-implementation.md`

It does **not** reopen product direction. Its only job is to decide whether Stage 2 is complete enough to move forward, or whether one more Stage 2 refinement pass is still required.

## Why This Plan Comes Next

Stage 2D hardening is now merged on `master`, and the evidence path from coding and insights into the final Markdown report is in place. The next unanswered question is no longer plumbing correctness in isolation. It is product credibility:

- does the full workflow behave well enough on realistic inputs
- are grounded outputs actually useful rather than merely structured
- are any remaining gaps true Stage 2 blockers or only polish

This plan answers those questions before any Stage 3 context-layer planning begins.

## Success Criteria

This closeout assessment is complete when:

- the full Stage 2 loop is exercised with realistic or near-realistic research inputs
- the team has a written scorecard for questionnaire grounding, coding quality, insight quality, and report quality
- blockers are clearly separated from non-blocking improvements
- the final assessment produces one of two recommendations:
  - `Stage 2 complete enough to start Stage 3 planning`
  - `Stage 2 needs one more refinement pass`

## Non-Goals

- no Stage 3 Research Brief, Task Plan, or project-home redesign work
- no north-star changes
- no broad retrieval redesign unless acceptance findings prove it is a blocker
- no UI expansion beyond what is needed to run and inspect the acceptance flow
- no opportunistic analytics feature expansion outside the closeout decision

---

## Task 1: Define the closeout rubric and realistic acceptance inputs

**Files:**
- Create: `docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-scorecard.md`
- Create: `docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-fixture-manifest.md`
- Create: `tests/fixtures/stage2_closeout/README.md`
- Create: `tests/fixtures/stage2_closeout/knowledge/`
- Create: `tests/fixtures/stage2_closeout/surveys/`
- Create: `tests/test_stage2_closeout_fixtures.py`

**Step 1: Write the failing test**

Create a focused fixture-manifest test that proves the closeout inputs exist and are shaped for the Stage 2 loop:

```python
from pathlib import Path


def test_stage2_closeout_fixtures_include_knowledge_and_survey_inputs():
    root = Path("tests/fixtures/stage2_closeout")

    assert (root / "README.md").exists()
    assert any((root / "knowledge").glob("*.md"))
    assert any((root / "surveys").glob("*.csv"))
```

**Step 2: Run the test to verify failure**

Run: `.venv/Scripts/python.exe -m pytest -v tests/test_stage2_closeout_fixtures.py`

Expected:
- FAIL because the closeout fixture directory and manifest files do not exist yet

**Step 3: Write the minimal implementation**

Add a realistic acceptance-input set that stays inside current Stage 2 scope:

- at least 2 knowledge documents representing realistic survey-research guidance
- at least 1 survey file with:
  - `metadata`
  - `scale`
  - `single_choice`
  - `free_text` and/or `other_text` linkage
- a fixture README that explains why these inputs were chosen
- a scorecard doc with these sections:
  - Input realism
  - Questionnaire grounding
  - Coding usefulness
  - Insight usefulness
  - Report clarity
  - Final recommendation
- a fixture manifest that maps each file to the workflow step it is meant to stress

Keep the fixture set small. The point is realism, not volume.

**Step 4: Run the tests to verify pass**

Run:

```bash
.venv/Scripts/python.exe -m pytest -v tests/test_stage2_closeout_fixtures.py
.venv/Scripts/python.exe -m pytest -v tests/test_real_sample_understanding.py tests/test_upload_contract.py
```

Expected:
- PASS
- no regression in upload-contract and real-sample expectations

**Step 5: Commit**

```bash
git add docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-scorecard.md docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-fixture-manifest.md tests/fixtures/stage2_closeout tests/test_stage2_closeout_fixtures.py
git commit -m "test: add stage 2 closeout acceptance fixtures"
```

---

## Task 2: Add a dedicated closeout acceptance harness

**Files:**
- Create: `scripts/run_stage2_closeout_assessment.py`
- Modify: `scripts/verify_local_http.py`
- Create: `tests/test_stage2_closeout_assessment.py`

**Step 1: Write the failing test**

Add a focused test for the new harness:

```python
def test_stage2_closeout_assessment_script_emits_key_artifact_paths(monkeypatch, tmp_path):
    ...
    assert "QUESTIONNAIRE_PATH=" in output
    assert "CODING_THEMES_PRESENT=True" in output
    assert "INSIGHT_EVIDENCE_PRESENT=True" in output
    assert "REPORT_EVIDENCE_SECTION_COUNT=1" in output
```

**Step 2: Run the test to verify failure**

Run: `.venv/Scripts/python.exe -m pytest -v tests/test_stage2_closeout_assessment.py`

Expected:
- FAIL because the harness script does not exist yet

**Step 3: Write the minimal implementation**

Create a dedicated assessment script that:

- seeds a temporary workspace from `tests/fixtures/stage2_closeout`
- starts the app locally, following the existing `scripts/verify_local_http.py` pattern
- executes the full Stage 2 loop:
  - ingest knowledge
  - create project
  - generate questionnaire draft
  - import dataset
  - run text coding using only `analysis_run_id` + `question_column`
  - run insight synthesis using only `analysis_run_id` + `research_goal`
  - generate report
- prints machine-readable summary lines, including:
  - `QUESTIONNAIRE_PATH=...`
  - `CODING_THEMES_PRESENT=True/False`
  - `INSIGHT_EVIDENCE_PRESENT=True/False`
  - `REPORT_EVIDENCE_SECTION_COUNT=<n>`
  - `REPORT_PATH=...`

Prefer reusing shared helper patterns from `scripts/verify_local_http.py` rather than duplicating server boot logic.

**Step 4: Run the tests to verify pass**

Run:

```bash
.venv/Scripts/python.exe -m pytest -v tests/test_stage2_closeout_assessment.py
.venv/Scripts/python.exe scripts/run_stage2_closeout_assessment.py
```

Expected:
- pytest PASS
- script runs end to end and prints the expected summary lines

**Step 5: Commit**

```bash
git add scripts/run_stage2_closeout_assessment.py scripts/verify_local_http.py tests/test_stage2_closeout_assessment.py
git commit -m "test: add stage 2 closeout acceptance harness"
```

---

## Task 3: Harden acceptance assertions around grounded outputs

**Files:**
- Modify: `tests/test_end_to_end_smoke.py`
- Modify: `tests/test_questionnaire_service.py`
- Modify: `tests/test_insights_service.py`
- Modify: `tests/test_reporting.py`

**Step 1: Write the failing tests**

Extend the current acceptance-facing coverage so the closeout decision is based on grounded output quality, not just route success:

```python
def test_questionnaire_draft_includes_visible_knowledge_basis_with_realistic_fixture(...):
    ...


def test_stage2_closeout_flow_produces_coding_insight_and_single_report_evidence_section(...):
    ...
    assert coding["themes"]
    assert insights["evidence_section"].startswith("## Evidence Basis")
    assert report_markdown.count("## Evidence Basis") == 1
```

**Step 2: Run the tests to verify failure**

Run:

```bash
.venv/Scripts/python.exe -m pytest -v tests/test_end_to_end_smoke.py tests/test_questionnaire_service.py tests/test_insights_service.py tests/test_reporting.py
```

Expected:
- FAIL until the new acceptance assertions are wired to the closeout fixtures or script outputs

**Step 3: Write the minimal implementation**

Only add the smallest missing glue needed for acceptance visibility:

- reuse the closeout fixtures in the smoke path where appropriate
- expose any missing output details needed to inspect the loop
- do **not** broaden feature scope
- do **not** change north-star or start Stage 3 work

If a test fails because the current output is genuinely weak rather than just under-asserted, record that as a closeout finding instead of silently making the product smarter in this task.

**Step 4: Run the tests to verify pass**

Run:

```bash
.venv/Scripts/python.exe -m pytest -v tests/test_end_to_end_smoke.py tests/test_questionnaire_service.py tests/test_insights_service.py tests/test_reporting.py
```

Expected:
- PASS

**Step 5: Commit**

```bash
git add tests/test_end_to_end_smoke.py tests/test_questionnaire_service.py tests/test_insights_service.py tests/test_reporting.py
git commit -m "test: harden stage 2 closeout acceptance assertions"
```

---

## Task 4: Run the realistic closeout assessment and write the result report

**Files:**
- Create: `docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-report.md`
- Modify: `docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-scorecard.md`

**Step 1: Prepare the report template**

Create the result report with these sections:

- Assessment date
- Inputs used
- Questionnaire observations
- Coding observations
- Insight observations
- Report observations
- Blockers
- Non-blocking improvements
- Recommendation

**Step 2: Run the acceptance harness**

Run:

```bash
.venv/Scripts/python.exe scripts/run_stage2_closeout_assessment.py
.venv/Scripts/python.exe -m pytest -v tests/test_stage2_closeout_assessment.py tests/test_end_to_end_smoke.py
```

Expected:
- the script finishes successfully
- the closeout smoke tests pass

**Step 3: Inspect the generated artifacts**

Manually inspect:

- generated questionnaire Markdown
- coding output themes and examples
- insight narrative and evidence section
- final report Markdown

Use the scorecard to mark each area as:

- `credible`
- `usable but weak`
- `blocking`

**Step 4: Write the closeout report**

Fill in the report with:

- what worked
- what felt weak
- what is a true Stage 2 blocker
- what is merely polish

Do not rewrite product direction in this report.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-scorecard.md docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-report.md
git commit -m "docs: record stage 2 closeout assessment"
```

---

## Task 5: Turn the assessment into a go/no-go Stage 2 decision

**Files:**
- Modify: `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`
- Create if needed: `docs/plans/2026-03-13-game-survey-workbench-stage-2-refinement-plan.md`
- Create if ready: `docs/plans/2026-03-13-game-survey-workbench-stage-3-context-layer-plan.md`

**Step 1: Re-read the closeout report and north-star plan**

Confirm whether the acceptance evidence supports:

- `Stage 2 complete enough`
- or `one more Stage 2 refinement pass`

**Step 2: Take only one of these branches**

If Stage 2 is complete enough:

- update the north-star tail status to reflect Stage 2 closeout completed
- draft the Stage 3 plan next

If Stage 2 still has blockers:

- keep Stage 3 deferred
- write a narrowly scoped Stage 2 refinement plan tied directly to the blockers

**Step 3: Verify the recommendation is evidence-backed**

Run:

```bash
.venv/Scripts/python.exe -m pytest -v
.venv/Scripts/python.exe -m compileall src
```

Expected:
- the recommendation is paired with fresh verification evidence and the written closeout findings

**Step 4: Commit**

Choose one:

```bash
git add docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md docs/plans/2026-03-13-game-survey-workbench-stage-3-context-layer-plan.md
git commit -m "docs: close out stage 2 and start stage 3 planning"
```

or

```bash
git add docs/plans/2026-03-13-game-survey-workbench-stage-2-refinement-plan.md
git commit -m "docs: plan final stage 2 refinement pass"
```

---

## Verification Checklist Before Any Completion Claim

- Run: `.venv/Scripts/python.exe -m pytest -v`
- Run: `.venv/Scripts/python.exe -m compileall src`
- Run: `.venv/Scripts/python.exe scripts/run_stage2_closeout_assessment.py`
- Confirm manually:
  - the questionnaire output shows visible grounding
  - coding uses persisted run data, not request-body responses
  - insight synthesis uses saved coding results and deterministic findings from the saved run
  - the final report contains exactly one clean `## Evidence Basis` section
  - the closeout recommendation is supported by the written scorecard and report

## Manual Acceptance Inputs

Use these principles when selecting or curating closeout fixtures:

1. **Knowledge input realism:** at least one document should reflect actual survey-design or interpretation guidance rather than toy placeholder content.

2. **Survey input realism:** the dataset should contain mixed question types and at least one free-text or other-text path that exercises the analysis-side LLM flow.

3. **Report usefulness realism:** the final report should be plausible for a researcher to edit and reuse, not merely structurally valid Markdown.

## Notes

- This plan is intentionally acceptance-first, not architecture-expansion-first.
- If the assessment reveals a blocker, document it before fixing it.
- Do not silently convert closeout findings into opportunistic Stage 3 work.
- Prefer a small number of realistic fixtures over a large number of synthetic ones.
