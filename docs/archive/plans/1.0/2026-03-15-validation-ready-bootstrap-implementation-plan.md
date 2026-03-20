# Validation Ready Bootstrap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the app easier to validate locally with real data by adding bootstrap docs/scripts and graceful missing-LLM browser fallbacks.

**Architecture:** Keep the runtime model unchanged and layer the improvements at the edges: environment-template docs at the repo root, a Windows startup script that loads `.env`, and minimal form-route fallback handling that reuses existing workflow error display for analysis-backed pages. Questionnaire flows use a page-level error query flag instead of new persistence.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLModel, pytest, Windows batch, uv

---

### Task 1: Add Missing-LLM Form Fallback Tests

**Files:**
- Create: `tests/test_validation_ready_llm_fallback.py`

**Step 1: Write the failing test**

- cover questionnaire draft form redirect + page message
- cover text coding / insights / report form redirects + persisted workflow error
- cover analysis detail page message rendering

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_validation_ready_llm_fallback.py -v`

**Step 3: Implement minimal route/template changes**

- handle `MissingLLMConfigurationError` in form routes
- use workflow state for analysis flows
- use query parameter for questionnaire flow

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_validation_ready_llm_fallback.py -v`

### Task 2: Add `.env.example` and `run.bat`

**Files:**
- Create: `.env.example`
- Create: `run.bat`

**Step 1: Add `.env.example`**

- list all supported environment variables
- include commented OpenAI and Ollama examples

**Step 2: Add `run.bat`**

- copy `.env.example` to `.env` and exit if `.env` is missing
- load `.env`
- run `uv sync`
- open browser
- start Uvicorn via factory mode

**Step 3: Run full test suite**

Run: `python -m pytest --tb=short -q`

### Task 3: Update README

**Files:**
- Modify: `README.md`

**Step 1: Add Quick Start**

- clone
- configure `.env`
- run `run.bat`

**Step 2: Add LLM configuration section**

- `openai_compatible`
- `fake`

**Step 3: Add first-run workflow summary**

- create project
- import data
- run questionnaire / coding / insights / report

**Step 4: Run full test suite**

Run: `python -m pytest --tb=short -q`

### Task 4: Final Verification and Commit

**Files:**
- Verify all staged files

**Step 1: Run full test suite**

Run: `python -m pytest --tb=short -q`

**Step 2: Commit**

```bash
git add .env.example run.bat README.md src/game_survey_workbench/routes/text_coding.py src/game_survey_workbench/routes/insights.py src/game_survey_workbench/routes/questionnaires.py src/game_survey_workbench/routes/reports.py src/game_survey_workbench/templates/questionnaires/detail.html tests/test_validation_ready_llm_fallback.py docs/plans/2026-03-15-validation-ready-bootstrap-design.md docs/plans/2026-03-15-validation-ready-bootstrap-implementation-plan.md
git commit -m "chore: add validation-ready bootstrap (env, LLM fallback, startup script)"
```
