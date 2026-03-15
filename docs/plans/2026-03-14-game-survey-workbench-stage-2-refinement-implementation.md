# Stage 2 Refinement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the Stage 2 credibility gap by strengthening prompt quality, improving report readability, and adding a dual-mode closeout harness so the product can be judged on real LLM output — not just scripted plumbing.

**Architecture:** Keep the existing monolith untouched. Changes are limited to prompt files, the closeout assessment script, the report template, and their tests. No new models, no new routes, no new services.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, pytest, Jinja2, Markdown prompts

---

## Stage Assessment

**Judgment:** Continue Stage 2 refinement. The existing refinement plan (2026-03-13) was written but never executed — no commits exist after `fa635b6`.

**Evidence:**
- North Star (line 266-267): closeout recommendation is "one more Stage 2 refinement pass"
- Closeout Scorecard: questionnaire "usable but weak", insight "usable but weak", report "usable but weak"
- Closeout Report (line 68): "The next step should stay inside Stage 2"
- Git history: zero implementation commits after planning docs

**No conflicts detected** with north-star or closeout report. No new evidence overrides the recommendation.

---

## Relationship to Existing Plans

This plan **replaces** `docs/plans/2026-03-13-game-survey-workbench-stage-2-refinement-plan.md` with a more granular, TDD-driven version of the same scope.

It follows:
- `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`
- `docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-scorecard.md`
- `docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-report.md`

## Success Criteria

1. Questionnaire prompt produces output with segmentation guidance, question rationale, and diagnostic framing — verified by test assertion on prompt content
2. Insight synthesis prompt produces output with actionable structure and concise evidence referencing — verified by test assertion on prompt content
3. Report template renders a tighter executive summary and scannable evidence section — verified by template rendering tests
4. Closeout script supports `--mode provider` alongside the existing scripted default — verified by unit test and manual run
5. All existing tests continue to pass with zero regressions

## Non-Goals

- No Stage 3 Research Brief or Task Plan work
- No north-star changes
- No new models, routes, or services
- No retrieval pipeline redesign
- No dashboard/BI output format

---

## Task 1: Strengthen the questionnaire design prompt

The current prompt at `src/game_survey_workbench/llm/prompts/questionnaire_design.md` is 11 lines with 5 generic requirements. The closeout assessment found the output "thin" — no segmentation guidance, no question rationale, no diagnostic framing. This task rewrites the prompt to ask for richer output without changing the service code.

**Files:**
- Modify: `src/game_survey_workbench/llm/prompts/questionnaire_design.md`
- Modify: `tests/test_questionnaire_service.py`

**Step 1: Write a test that asserts the prompt contains the new quality signals**

Add to `tests/test_questionnaire_service.py`:

```python
def test_questionnaire_prompt_requests_segmentation_and_rationale():
    prompt = load_questionnaire_prompt()

    assert "segment" in prompt.lower(), "Prompt should request segmentation-aware questions"
    assert "rationale" in prompt.lower() or "why" in prompt.lower(), "Prompt should request question rationale"
    assert "diagnostic" in prompt.lower() or "follow-up" in prompt.lower(), "Prompt should request diagnostic framing"
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_questionnaire_service.py::test_questionnaire_prompt_requests_segmentation_and_rationale -v`

Expected: FAIL — current prompt does not contain "segment", "rationale", or "diagnostic"

**Step 3: Rewrite the questionnaire design prompt**

Replace `src/game_survey_workbench/llm/prompts/questionnaire_design.md` with:

```markdown
# Questionnaire Design Prompt

Use the supplied project context, research goal, hypotheses, and knowledge snippets
to draft a Markdown questionnaire spec that remains easy to edit manually.

## Output Structure

Organize the questionnaire into clear thematic sections. Each section should:

1. State a brief **section rationale** — why this group of questions matters to the research goal.
2. List 2-5 questions per section.
3. For each question, add a one-line **diagnostic note** explaining what the question is designed to reveal and how a researcher should read the answers.

## Segmentation Awareness

- If the knowledge or hypotheses mention distinct player segments (e.g., payers vs. free users, new vs. returning), include at least one question that helps distinguish segment-specific experiences.
- Where a follow-up or branching question would improve segment clarity, note it explicitly.

## Question Quality

- Keep questions aligned with the stated research goal and hypotheses.
- Prefer concrete, behavioral wording over vague satisfaction scales.
- Use the supplied knowledge as grounding — reference it in rationale where relevant.
- Do not invent citations or claim unsupported evidence.

## Format

- Output valid, editable Markdown.
- Use `##` for section headings, `-` for question lists, and `>` for diagnostic notes.
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_questionnaire_service.py::test_questionnaire_prompt_requests_segmentation_and_rationale -v`

Expected: PASS

**Step 5: Run full questionnaire test suite to check for regressions**

Run: `.venv/Scripts/python.exe -m pytest tests/test_questionnaire_service.py -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/game_survey_workbench/llm/prompts/questionnaire_design.md tests/test_questionnaire_service.py
git commit -m "feat: strengthen questionnaire design prompt with segmentation and rationale"
```

---

## Task 2: Strengthen the insight synthesis prompt

The current prompt at `src/game_survey_workbench/llm/prompts/insight_synthesis.md` is 22 lines with generic constraints. The closeout found that insight output "reads mechanically." This task rewrites the prompt to request a structured executive takeaway, actionable recommendations, and concise evidence references.

**Files:**
- Modify: `src/game_survey_workbench/llm/prompts/insight_synthesis.md`
- Modify: `tests/test_insights_service.py`

**Step 1: Write a test that asserts the prompt contains the new quality signals**

Add to `tests/test_insights_service.py`:

```python
def test_insight_prompt_requests_executive_takeaway_and_recommendations():
    prompt = load_insight_prompt()

    assert "executive" in prompt.lower() or "takeaway" in prompt.lower(), "Prompt should request an executive takeaway"
    assert "recommend" in prompt.lower() or "action" in prompt.lower(), "Prompt should request actionable recommendations"
    assert "concise" in prompt.lower() or "brief" in prompt.lower(), "Prompt should request concise evidence references"
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_insights_service.py::test_insight_prompt_requests_executive_takeaway_and_recommendations -v`

Expected: FAIL — current prompt has "concise" but not "executive"/"takeaway" or "recommend"/"action"

**Step 3: Rewrite the insight synthesis prompt**

Replace `src/game_survey_workbench/llm/prompts/insight_synthesis.md` with:

```markdown
# Insight Synthesis Prompt

Write Markdown insight synthesis for a game survey analysis workflow.

## Input

- Research goal
- Statistical findings (deterministic, pre-computed)
- Coded open-text themes (from prior coding step)
- Retrieved knowledge snippets (from project knowledge base)

## Output Structure

### 1. Executive Takeaway (1-2 sentences)

Open with the single most important finding that a decision-maker needs to hear. Ground it in a specific stat or coded theme.

### 2. Supporting Analysis (2-4 paragraphs)

- Connect statistical findings, coded themes, and knowledge where they reinforce each other.
- Use brief inline citations — e.g., "(per Churn Framework)" or "(coded theme: Boredom, n=12)" — rather than pasting long excerpts.
- Call out contradictions or gaps explicitly rather than ignoring them.

### 3. Recommended Actions (2-4 bullets)

- Each recommendation should be concrete and tied to a specific finding.
- Frame recommendations as "Consider X because Y" rather than vague "improve the experience."

## Constraints

- Every claim must point back to a stat finding, coded theme, or knowledge source.
- Do not fabricate evidence.
- Keep the output in Markdown prose suitable for a report section.
- Be concise — the full narrative should fit in roughly 200-400 words.
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_insights_service.py::test_insight_prompt_requests_executive_takeaway_and_recommendations -v`

Expected: PASS

**Step 5: Run full insight test suite to check for regressions**

Run: `.venv/Scripts/python.exe -m pytest tests/test_insights_service.py -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/game_survey_workbench/llm/prompts/insight_synthesis.md tests/test_insights_service.py
git commit -m "feat: strengthen insight synthesis prompt with executive takeaway and recommendations"
```

---

## Task 3: Improve report template readability

The current report template at `src/game_survey_workbench/templates/reports/report.md.j2` renders evidence items as raw `title: content` strings, which the closeout found "pastes long source excerpts with limited summarization." This task tightens the evidence rendering and adds a report date.

**Files:**
- Modify: `src/game_survey_workbench/templates/reports/report.md.j2`
- Modify: `tests/test_reporting.py`

**Step 1: Write a test for the improved template rendering**

Add to `tests/test_reporting.py`:

```python
def test_render_report_markdown_includes_report_date():
    from datetime import date

    markdown = render_report_markdown(
        title="Churn Report",
        summary_points=["Boredom is the top driver."],
        sections={"Key Findings": ["Top box dropped to 32%."]},
    )

    assert "Report generated" in markdown or date.today().isoformat() in markdown


def test_render_report_markdown_evidence_fallback_uses_titles_only_when_content_is_long():
    markdown = render_report_markdown(
        title="Churn Report",
        summary_points=["Summary."],
        sections={},
        evidence=[
            {
                "document_title": "Churn Framework",
                "content": "A" * 300,
            },
        ],
    )

    assert "## Evidence Basis" in markdown
    assert "Churn Framework" in markdown
    # Long content should be truncated in the fallback rendering
    assert "A" * 300 not in markdown
```

**Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_reporting.py::test_render_report_markdown_includes_report_date tests/test_reporting.py::test_render_report_markdown_evidence_fallback_uses_titles_only_when_content_is_long -v`

Expected: FAIL

**Step 3: Update the report template**

Replace `src/game_survey_workbench/templates/reports/report.md.j2` with:

```jinja2
# {{ title }}

*Report generated {{ now }}*

## Executive Summary
{% for point in summary_points %}
- {{ point }}
{% endfor %}

{% if narrative %}
## Key Findings

{{ narrative }}

{% endif %}
{% for heading, items in sections.items() %}
## {{ heading }}
{% for item in items %}
- {{ item }}
{% endfor %}

{% endfor %}
{% if evidence_section %}
{{ evidence_section }}
{% elif evidence %}
## Evidence Basis
{% for item in evidence %}
- **{{ item.document_title }}**{% if item.content and item.content|length <= 200 %}: {{ item.content }}{% elif item.content %}: {{ item.content[:200] }}…{% endif %}

{% endfor %}
{% endif %}
```

**Step 4: Update `render_report_markdown` to pass `now` to the template**

Modify `src/game_survey_workbench/services/reporting.py` — update the `render_report_markdown` function:

```python
def render_report_markdown(
    title: str,
    summary_points: list[str],
    sections: dict[str, list[str]],
    narrative: str | None = None,
    evidence: list[dict] | None = None,
    evidence_section: str | None = None,
) -> str:
    from datetime import date

    template = get_environment().get_template("reports/report.md.j2")
    return template.render(
        title=title,
        summary_points=summary_points,
        sections=sections,
        narrative=narrative,
        evidence=evidence or [],
        evidence_section=evidence_section,
        now=date.today().isoformat(),
    )
```

**Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_reporting.py::test_render_report_markdown_includes_report_date tests/test_reporting.py::test_render_report_markdown_evidence_fallback_uses_titles_only_when_content_is_long -v`

Expected: PASS

**Step 6: Run full reporting test suite to check for regressions**

Run: `.venv/Scripts/python.exe -m pytest tests/test_reporting.py -v`

Expected: All tests PASS. If any existing test breaks due to the new `*Report generated...*` line, update that test's assertion to account for the new line.

**Step 7: Commit**

```bash
git add src/game_survey_workbench/templates/reports/report.md.j2 src/game_survey_workbench/services/reporting.py tests/test_reporting.py
git commit -m "feat: improve report template with date, bold titles, and evidence truncation"
```

---

## Task 4: Add dual-mode closeout assessment (scripted + provider)

The closeout script currently only runs with monkeypatched fake LLM output. This task adds a `--mode provider` flag that uses the real configured LLM client when credentials are present, while keeping `--mode scripted` as the default for regression safety.

**Files:**
- Modify: `scripts/run_stage2_closeout_assessment.py`
- Modify: `tests/test_stage2_closeout_assessment.py`

**Step 1: Write a test for the new mode metadata in output**

Add to `tests/test_stage2_closeout_assessment.py`:

```python
def test_stage2_closeout_assessment_script_emits_mode_metadata(monkeypatch, capsys):
    module = importlib.import_module("scripts.run_stage2_closeout_assessment")

    monkeypatch.setattr(
        module,
        "run_stage2_closeout_assessment",
        lambda mode="scripted": {
            "MODE": "scripted",
            "QUESTIONNAIRE_PATH": "workspace/projects/demo/questionnaire/versions/demo.md",
            "QUESTIONNAIRE_HAS_KNOWLEDGE_BASIS": True,
            "CODING_THEMES_PRESENT": True,
            "INSIGHT_EVIDENCE_PRESENT": True,
            "REPORT_EVIDENCE_SECTION_COUNT": 1,
            "REPORT_PATH": "workspace/projects/demo/reports/report-demo.md",
        },
    )

    module.main()
    output = capsys.readouterr().out

    assert "MODE=scripted" in output
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage2_closeout_assessment.py::test_stage2_closeout_assessment_script_emits_mode_metadata -v`

Expected: FAIL — `main()` currently calls `run_stage2_closeout_assessment()` without `mode` argument, and the function doesn't accept one

**Step 3: Add `mode` parameter to `run_stage2_closeout_assessment` and `main`**

Modify `scripts/run_stage2_closeout_assessment.py`:

At the top, add `import argparse` and `import sys` to existing imports.

Replace the `run_stage2_closeout_assessment` function signature and the monkeypatching block:

```python
def run_stage2_closeout_assessment(mode: str = "scripted") -> dict[str, str | bool | int]:
    workspace_root = create_workspace_root()
    port = find_free_port()

    previous_workspace_root = os.environ.get("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT")
    os.environ["GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT"] = str(workspace_root)

    original_generate = None
    original_llm_env = None

    if mode == "scripted":
        original_llm_env = configure_fake_llm_environment()
        original_generate = OpenAICompatibleLLMClient.generate
        OpenAICompatibleLLMClient.generate = fake_llm_generate
    else:
        # In provider mode, verify that real credentials are present
        required_vars = [
            "GAME_SURVEY_WORKBENCH_LLM_PROVIDER",
            "GAME_SURVEY_WORKBENCH_LLM_MODEL",
            "GAME_SURVEY_WORKBENCH_LLM_API_KEY",
            "GAME_SURVEY_WORKBENCH_LLM_BASE_URL",
        ]
        missing = [v for v in required_vars if not os.environ.get(v)]
        if missing:
            raise RuntimeError(
                f"Provider mode requires these environment variables: {', '.join(missing)}"
            )

    try:
        seed_stage2_closeout_workspace(workspace_root)
        ingest_closeout_knowledge(workspace_root)

        with run_local_server(port=port) as base_url:
            httpx.post(
                f"{base_url}/projects",
                json={"slug": PROJECT_SLUG, "name": PROJECT_NAME, "knowledge_pack": {}},
                timeout=5.0,
            ).raise_for_status()

            draft = httpx.post(
                f"{base_url}/projects/{PROJECT_SLUG}/questionnaires/draft",
                json={"research_goal": QUESTIONNAIRE_GOAL},
                timeout=30.0,
            )
            draft.raise_for_status()
            draft_payload = draft.json()
            questionnaire_path = (
                workspace_root
                / "projects"
                / PROJECT_SLUG
                / "questionnaire"
                / "versions"
                / f"{draft_payload['version_id']}.md"
            )
            questionnaire_markdown = questionnaire_path.read_text(encoding="utf-8")

            dataset_path = workspace_root / "projects" / PROJECT_SLUG / "data" / "raw" / DATASET_FILENAME
            dataset = httpx.post(
                f"{base_url}/projects/{PROJECT_SLUG}/datasets/import",
                files={"file": (DATASET_FILENAME, dataset_path.read_bytes(), "text/csv")},
                timeout=5.0,
            )
            dataset.raise_for_status()
            dataset_payload = dataset.json()
            analysis_run_id = dataset_payload["analysis_run_id"]

            coding = httpx.post(
                f"{base_url}/projects/{PROJECT_SLUG}/analysis/{analysis_run_id}/code-text",
                json={"question_column": CODING_QUESTION},
                timeout=30.0,
            )
            coding.raise_for_status()
            coding_payload = coding.json()

            insights = httpx.post(
                f"{base_url}/projects/{PROJECT_SLUG}/analysis/{analysis_run_id}/insights",
                json={"research_goal": INSIGHT_GOAL},
                timeout=30.0,
            )
            insights.raise_for_status()
            insight_payload = insights.json()

            report = httpx.post(
                f"{base_url}/projects/{PROJECT_SLUG}/reports/generate",
                json={"analysis_run_id": analysis_run_id},
                timeout=5.0,
            )
            report.raise_for_status()
            report_payload = report.json()

        report_path = Path(report_payload["path"])
        report_markdown = report_path.read_text(encoding="utf-8")

        return {
            "MODE": mode,
            "QUESTIONNAIRE_PATH": str(questionnaire_path),
            "QUESTIONNAIRE_HAS_KNOWLEDGE_BASIS": "## Knowledge Basis" in questionnaire_markdown,
            "CODING_THEMES_PRESENT": bool(coding_payload["themes"]),
            "INSIGHT_EVIDENCE_PRESENT": bool(insight_payload["evidence_section"].strip()),
            "REPORT_EVIDENCE_SECTION_COUNT": report_markdown.count("## Evidence Basis"),
            "REPORT_PATH": str(report_path),
        }
    finally:
        if original_generate is not None:
            OpenAICompatibleLLMClient.generate = original_generate
        if original_llm_env is not None:
            restore_environment(original_llm_env)
        if previous_workspace_root is None:
            os.environ.pop("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", None)
        else:
            os.environ["GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT"] = previous_workspace_root
```

Replace `main`:

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage 2 closeout assessment")
    parser.add_argument(
        "--mode",
        choices=["scripted", "provider"],
        default="scripted",
        help="scripted (default): use fake LLM output; provider: use real configured LLM",
    )
    args = parser.parse_args()

    results = run_stage2_closeout_assessment(mode=args.mode)
    for key, value in results.items():
        print(f"{key}={value}")
```

**Step 4: Run the new test**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage2_closeout_assessment.py::test_stage2_closeout_assessment_script_emits_mode_metadata -v`

Expected: PASS

**Step 5: Write a test that provider mode rejects missing credentials**

Add to `tests/test_stage2_closeout_assessment.py`:

```python
def test_stage2_closeout_assessment_provider_mode_rejects_missing_credentials(monkeypatch):
    module = importlib.import_module("scripts.run_stage2_closeout_assessment")

    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", raising=False)
    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="Provider mode requires"):
        module.run_stage2_closeout_assessment(mode="provider")
```

(Add `import pytest` at the top of the file if not already present.)

**Step 6: Run the new test**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage2_closeout_assessment.py::test_stage2_closeout_assessment_provider_mode_rejects_missing_credentials -v`

Expected: PASS

**Step 7: Update the existing output test to include MODE**

Update `test_stage2_closeout_assessment_script_emits_key_artifact_paths` — the monkeypatched lambda should accept `mode="scripted"` and the returned dict should include `"MODE": "scripted"`. Add `assert "MODE=" in output` to the assertions.

**Step 8: Run full closeout test suite**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage2_closeout_assessment.py -v`

Expected: All tests PASS

**Step 9: Commit**

```bash
git add scripts/run_stage2_closeout_assessment.py tests/test_stage2_closeout_assessment.py
git commit -m "feat: add dual-mode closeout assessment with provider mode and credential validation"
```

---

## Task 5: Full regression check and closeout harness smoke test

This task runs the complete test suite and the scripted closeout to verify that nothing is broken.

**Step 1: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest -v`

Expected: All tests PASS

**Step 2: Run compile check**

Run: `.venv/Scripts/python.exe -m compileall src`

Expected: All files compile without errors

**Step 3: Run the scripted closeout assessment**

Run: `.venv/Scripts/python.exe scripts/run_stage2_closeout_assessment.py`

Expected: All artifact flags show True/1, `MODE=scripted`

**Step 4: Commit if any fixups were needed**

Only commit if Task 5 required any fixups to earlier tasks.

---

## Task 6: Update closeout decision docs with refinement evidence

This is the final evaluation task. After Tasks 1-5 pass, re-assess the Stage 2 readiness.

**Files:**
- Modify: `docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-scorecard.md`
- Modify: `docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-report.md`

**Step 1: Run the scripted closeout and inspect artifact quality**

Run: `.venv/Scripts/python.exe scripts/run_stage2_closeout_assessment.py`

Manually verify:
- The questionnaire prompt now requests segmentation, rationale, and diagnostic framing
- The insight prompt now requests executive takeaway, supporting analysis, and recommendations
- The report template renders with a date, bold evidence titles, and truncated long excerpts

**Step 2: If credentials are available, run provider-backed closeout**

Run: `.venv/Scripts/python.exe scripts/run_stage2_closeout_assessment.py --mode provider`

Manually inspect the generated questionnaire, insight narrative, and report at the printed paths. Evaluate whether the real LLM output meets researcher usefulness.

**Step 3: Update the closeout scorecard**

Based on the evidence from Steps 1-2, update each dimension in `docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-scorecard.md`:
- Record the new assessment for each dimension
- Update the final recommendation (either "Stage 2 complete — ready for Stage 3 planning" or "Stage 2 needs another pass" with specific blockers)

**Step 4: Update the closeout report**

Update `docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-report.md`:
- Record the new observations for each section
- If provider-backed evidence was captured, note the artifacts and their quality
- Update the final recommendation

**Step 5: Commit**

```bash
git add docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-scorecard.md docs/plans/2026-03-13-game-survey-workbench-stage-2-closeout-report.md
git commit -m "docs: update closeout assessment after stage 2 refinement pass"
```

**Step 6: If Stage 2 is now complete, update the north-star status**

Only if the closeout evidence supports it, update `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`:
- Change closeout recommendation to "Stage 2 complete"
- Update status to indicate Stage 3 planning can begin

```bash
git add docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md
git commit -m "docs: mark stage 2 complete in north-star plan"
```

---

## Verification Checklist Before Any Completion Claim

- [ ] `.venv/Scripts/python.exe -m pytest -v` — all pass
- [ ] `.venv/Scripts/python.exe -m compileall src` — no errors
- [ ] `.venv/Scripts/python.exe scripts/run_stage2_closeout_assessment.py` — all artifact flags True/1
- [ ] Questionnaire prompt contains segmentation, rationale, and diagnostic keywords
- [ ] Insight prompt contains executive takeaway, recommendations, and concise references
- [ ] Report template renders date, bold evidence titles, and truncated long excerpts
- [ ] Closeout scorecard and report are updated with fresh evidence
- [ ] No new models, routes, or services were created
- [ ] No north-star product direction changes were made

## Notes

- Tasks 1-3 (prompt + template improvements) are independent and could be parallelized
- Task 4 (dual-mode closeout) depends on Tasks 1-3 being complete to produce meaningful provider-backed output
- Task 5 (regression check) must run after Tasks 1-4
- Task 6 (decision docs) must run last and requires human judgment for the go/no-go call
- The provider-backed closeout (Task 6 Step 2) is conditional on credentials being available — it is not a blocking requirement for the scripted regression
