# Stage 2 Closeout Fixture Manifest

This manifest keeps the acceptance fixture set intentionally small while mapping each input to the Stage 2 workflow step it is meant to stress.

| File | Type | Workflow step stressed | Why it matters |
| --- | --- | --- | --- |
| `tests/fixtures/stage2_closeout/knowledge/live_ops_survey_design.md` | Knowledge doc | Questionnaire design grounding | Captures how to frame survey prompts around progression clarity, value, and live-ops trust. |
| `tests/fixtures/stage2_closeout/knowledge/free_text_interpretation.md` | Knowledge doc | Coding and insight synthesis grounding | Gives interpretation guidance for recurring free-text complaints and improvement requests. |
| `tests/fixtures/stage2_closeout/surveys/season_pass_closeout.csv` | Survey dataset | Data import, coding, insight synthesis, report generation | Exercises metadata, scale, single-choice, free-text, and other-text linkage in one realistic pass. |
| `tests/fixtures/stage2_closeout/README.md` | Fixture notes | Assessment framing | Explains why these inputs are credible enough for Stage 2 closeout validation. |
