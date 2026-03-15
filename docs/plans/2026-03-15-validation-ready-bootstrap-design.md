# Validation Ready Bootstrap Design

**Date:** 2026-03-15

## Goal

Make the local product easier to validate with real data and a real LLM setup, while keeping the implementation small, explicit, and low-risk.

## Constraints

- no new dependencies
- no core model changes
- no UI redesign
- keep behavior changes focused on startup/bootstrap and friendly failure handling

## Scope

1. add a root `.env.example` with all supported environment variables
2. make form-based LLM actions fail gracefully when the LLM is not configured
3. add a Windows `run.bat` bootstrap script
4. extend `README.md` with quick-start and LLM setup guidance
5. add regression tests for the new fallback behavior

## Design Decisions

### 1. `.env` loading stays in the startup script

The application currently reads configuration from process environment variables only. To keep the patch small, the app will continue doing that. `run.bat` will load `.env` into the process before starting Uvicorn.

### 2. Startup is intentionally blocking without `.env`

If `.env` is missing, `run.bat` will copy `.env.example` and exit immediately with instructions to complete real LLM configuration before retrying. This matches the product goal of validating the complete experience rather than just rendering the UI.

### 3. Form routes get friendly degradation

When a user triggers questionnaire generation, text coding, insights, or report generation from the browser and the LLM is not configured:

- analysis-backed flows will record a workflow failure using the existing `workflow_state.last_error` path
- the user will be redirected back to the originating page
- the page will show a consistent Chinese message: `LLM 未配置，请设置环境变量后重试`

### 4. Questionnaire page uses page-level error messaging

Questionnaire draft generation is project-scoped rather than analysis-run-scoped, so it does not have an existing workflow-state record to attach to. Instead of changing data models, the form route will redirect with a query-string error flag and the questionnaire detail page will render the same Chinese message.

## Testing Strategy

- add route tests covering missing-LLM behavior for questionnaire, coding, insights, and report generation forms
- assert redirect behavior rather than server crashes
- assert workflow error persistence for analysis-backed flows
- assert questionnaire/analysis pages render the friendly message after redirect-compatible state is set
- run full `pytest` after each task batch

## Non-Goals

- automatic `.env` loading in the application runtime outside `run.bat`
- richer secrets management
- shell scripts for macOS/Linux
- broader error taxonomy cleanup
