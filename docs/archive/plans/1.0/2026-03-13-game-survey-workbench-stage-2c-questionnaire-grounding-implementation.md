# Game Survey Workbench Stage 2C Questionnaire Grounding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn questionnaire drafting into a knowledge-grounded workflow that generates editable Markdown drafts and saves reusable citation evidence.

**Architecture:** Keep the existing Python monolith and extend the questionnaire path from "save caller-provided snippets" to "retrieve project knowledge, assemble grounded context, call the configured LLM, and persist both Markdown and structured evidence." Stage 2C should reuse the deterministic retrieval and provider adapter completed in Stage 2A and 2B rather than introducing embedding upgrades here.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, pytest, uv

---

## Assumptions

- Product direction remains defined by `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`
- Stage scope remains defined by `docs/plans/2026-03-13-game-survey-workbench-stage-2-llm-knowledge-plan.md`
- Stage 2A and Stage 2B foundations are already complete on `master`
- Stage 2C should produce editable Markdown plus visible and structured grounding evidence
- Stage 2C should not introduce embedding retrieval changes

### Task 1: Expand questionnaire persistence for structured grounding evidence

**Files:**
- Modify: `src/game_survey_workbench/models/questionnaire.py`
- Modify: `tests/test_questionnaire_service.py`

**Step 1: Write the failing test**

```python
from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion


def test_questionnaire_spec_version_supports_citations_and_retrieved_snippets():
    version = QuestionnaireSpecVersion(
        project_slug="demo",
        version_id="v1",
        research_goal="Study returners",
        markdown_spec="# Draft",
        citations=[{"document_title": "Retention Framework"}],
        retrieved_snippets=[{"content": "Use behavior and attitude questions together."}],
    )

    assert version.citations[0]["document_title"] == "Retention Framework"
    assert version.retrieved_snippets[0]["content"] == "Use behavior and attitude questions together."
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_questionnaire_service.py -v`
Expected: FAIL because the questionnaire model does not yet include structured evidence fields.

**Step 3: Write minimal implementation**

Add JSON-backed fields to `QuestionnaireSpecVersion`:

```python
citations: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
retrieved_snippets: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
```

Keep `research_goal` and `markdown_spec` unchanged.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_questionnaire_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/questionnaire.py tests/test_questionnaire_service.py
git commit -m "feat: persist questionnaire grounding evidence"
```

### Task 2: Add grounded questionnaire context assembly and Markdown evidence section

**Files:**
- Modify: `src/game_survey_workbench/services/questionnaires.py`
- Modify: `tests/test_questionnaire_service.py`

**Step 1: Write the failing tests**

```python
from game_survey_workbench.services.questionnaires import (
    build_questionnaire_design_context,
    build_questionnaire_markdown,
)


def test_build_questionnaire_design_context_includes_grounding_metadata():
    context = build_questionnaire_design_context(
        project_name="Returners",
        research_goal="Understand why players came back",
        hypotheses=["Return is driven by version updates"],
        knowledge_snippets=[
            {
                "document_title": "Questionnaire Principles",
                "content": "Questions should stay tightly aligned to the research goal.",
                "tags": ["questionnaire"],
            }
        ],
    )

    assert "Questionnaire Principles" in context
    assert "Questions should stay tightly aligned to the research goal." in context


def test_build_questionnaire_markdown_appends_knowledge_basis_section():
    markdown = build_questionnaire_markdown(
        llm_output="# Questionnaire Draft\n\n## Core Questions\n- Why did you return?",
        citations=[
            {
                "document_title": "Questionnaire Principles",
                "content": "Questions should stay tightly aligned to the research goal.",
            }
        ],
    )

    assert "## Knowledge Basis" in markdown
    assert "Questionnaire Principles" in markdown
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_questionnaire_service.py -v`
Expected: FAIL because grounding metadata is not yet formatted and no helper appends a knowledge-basis section.

**Step 3: Write minimal implementation**

Update the questionnaire service so:

- `build_questionnaire_design_context()` accepts `list[dict]` knowledge items
- each knowledge item includes source metadata plus snippet text
- new `build_questionnaire_markdown()` appends a `## Knowledge Basis` section

Keep formatting simple and deterministic.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_questionnaire_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/questionnaires.py tests/test_questionnaire_service.py
git commit -m "feat: build grounded questionnaire markdown"
```

### Task 3: Add questionnaire draft orchestration with retrieval and LLM execution

**Files:**
- Modify: `src/game_survey_workbench/services/questionnaires.py`
- Modify: `src/game_survey_workbench/services/projects.py`
- Modify: `tests/test_questionnaire_service.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from game_survey_workbench.llm.client import FakeLLMClient
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.questionnaire import QuestionnaireDraftRequest
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.questionnaires import generate_questionnaire_draft


def test_generate_questionnaire_draft_uses_project_retrieval_and_persists_citations(tmp_path: Path):
    source = tmp_path / "principles.md"
    source.write_text(
        "---\n"
        "title: Questionnaire Principles\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - design\n"
        "scenario: onboarding\n"
        "---\n"
        "Questions should stay tightly aligned to the research goal.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)
    create_project(
        ProjectCreate(
            slug="returners",
            name="Returners",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["onboarding"]},
        ),
        workspace_root=tmp_path,
    )

    version = generate_questionnaire_draft(
        project_slug="returners",
        payload=QuestionnaireDraftRequest(
            research_goal="Understand why players came back",
            hypotheses=["Return is driven by version updates"],
        ),
        workspace_root=tmp_path,
        client=FakeLLMClient("# Questionnaire Draft\n\n## Core Questions\n- Why did you return?"),
    )

    assert "## Knowledge Basis" in version.markdown_spec
    assert version.citations[0]["document_title"] == "Questionnaire Principles"
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_questionnaire_service.py -v`
Expected: FAIL because no orchestration helper currently combines project lookup, retrieval, client generation, and structured persistence.

**Step 3: Write minimal implementation**

Add a new service function:

```python
def generate_questionnaire_draft(...):
    project = get_project(...)
    snippets = retrieve_project_knowledge(
        workspace_root=workspace_root,
        project_slug=project_slug,
        query=f"{payload.research_goal} {' '.join(payload.hypotheses)}",
        stages=["design"],
    )
    if not snippets:
        raise ValueError("No knowledge matched this questionnaire request.")
    context = build_questionnaire_design_context(...)
    llm_output = client.generate(context)
    markdown = build_questionnaire_markdown(llm_output=llm_output, citations=snippets)
    return save_questionnaire_draft(..., citations=snippets, retrieved_snippets=snippets, markdown_spec=markdown)
```

Keep the helper deterministic and avoid provider-specific logic in this layer.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_questionnaire_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/questionnaires.py src/game_survey_workbench/services/projects.py tests/test_questionnaire_service.py
git commit -m "feat: orchestrate grounded questionnaire drafting"
```

### Task 4: Update route behavior to use service-driven grounding and runtime client selection

**Files:**
- Modify: `src/game_survey_workbench/routes/questionnaires.py`
- Modify: `tests/test_html_routes.py`
- Create: `tests/test_questionnaire_routes.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file


def test_create_questionnaire_draft_route_returns_grounded_markdown(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "demo-model")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")

    source = tmp_path / "principles.md"
    source.write_text(
        "---\n"
        "title: Questionnaire Principles\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - design\n"
        "scenario: onboarding\n"
        "---\n"
        "Questions should stay tightly aligned to the research goal.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)

    client = TestClient(create_app())
    client.post(
        "/projects",
        json={
            "slug": "returners",
            "name": "Returners",
            "knowledge_pack": {"doc_types": ["theory"], "scenarios": ["onboarding"]},
        },
    )

    response = client.post(
        "/projects/returners/questionnaires/draft",
        json={
            "research_goal": "Understand why players came back",
            "hypotheses": ["Return is driven by version updates"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert "## Knowledge Basis" in payload["markdown_spec"]
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_questionnaire_routes.py -v`
Expected: FAIL because the route still saves caller-supplied snippets and does not build the runtime client automatically.

**Step 3: Write minimal implementation**

Update the route so it:

- loads the configured settings
- builds the runtime client with `build_llm_client()`
- delegates to `generate_questionnaire_draft()`
- returns the generated Markdown and structured citations

Keep 404 behavior for missing projects and surface 400/500-class failures clearly.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_questionnaire_routes.py tests/test_questionnaire_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/questionnaires.py tests/test_questionnaire_routes.py tests/test_questionnaire_service.py
git commit -m "feat: wire grounded questionnaire route"
```

### Task 5: Add prompt loading and clear fallback/error coverage

**Files:**
- Modify: `src/game_survey_workbench/services/questionnaires.py`
- Modify: `tests/test_questionnaire_service.py`

**Step 1: Write the failing tests**

```python
import pytest

from game_survey_workbench.llm.client import MissingLLMConfigurationError
from game_survey_workbench.models.questionnaire import QuestionnaireDraftRequest
from game_survey_workbench.services.questionnaires import generate_questionnaire_draft


def test_generate_questionnaire_draft_rejects_missing_knowledge(tmp_path):
    with pytest.raises(ValueError, match="No knowledge matched"):
        generate_questionnaire_draft(
            project_slug="missing",
            payload=QuestionnaireDraftRequest(research_goal="Study returners"),
            workspace_root=tmp_path,
            client=None,
        )


def test_load_questionnaire_prompt_contains_markdown_instruction():
    prompt = load_questionnaire_prompt()
    assert "Markdown" in prompt
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_questionnaire_service.py -v`
Expected: FAIL because prompt loading and explicit failure paths are incomplete.

**Step 3: Write minimal implementation**

Add prompt loading helper and make failure paths explicit:

- load `src/game_survey_workbench/llm/prompts/questionnaire_design.md`
- raise clear `ValueError` for missing project or missing knowledge
- keep runtime client construction outside this helper when possible so service tests can still use `FakeLLMClient`

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_questionnaire_service.py tests/test_questionnaire_routes.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/questionnaires.py src/game_survey_workbench/llm/prompts/questionnaire_design.md tests/test_questionnaire_service.py
git commit -m "feat: add questionnaire prompt loading and failure handling"
```

## Verification Checklist Before Any Implementation Claim

- Run: `python -m uv run pytest tests/test_questionnaire_service.py tests/test_questionnaire_routes.py tests/test_retrieval_service.py tests/test_llm_client.py tests/test_projects.py -v`
- Run: `python -m uv run pytest -v`
- Run: `python -m uv run python -m compileall src`
- Manually confirm:
  - questionnaire draft output is Markdown and includes `## Knowledge Basis`
  - citations and retrieved snippets are persisted with questionnaire versions
  - project knowledge-pack filters affect which evidence appears in the draft
  - missing knowledge and missing LLM configuration fail clearly

## Manual Acceptance Inputs

Use at least one lightweight knowledge document during development:

- `docs/templates/问卷设计原则demo.md`

Use these real acceptance scenarios after implementation:

1. `研究回归玩家的回归理由`
2. `研究付费玩家对于当前版本的满意度`

For the second scenario, hypotheses may be refined from:

- current version update content
- core-user definition
- game positioning

## Risks and Notes

- Do not bypass retrieval by hardcoding snippets in the route layer.
- Do not let provider-specific behavior leak into the questionnaire service.
- Keep Markdown as the editable artifact while preserving structured evidence for later workflows.
- Do not expand this plan into Stage 2D text coding or insight synthesis work.
