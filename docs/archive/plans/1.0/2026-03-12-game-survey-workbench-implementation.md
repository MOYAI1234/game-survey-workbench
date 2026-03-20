# Game Survey Workbench Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local-first game survey research workbench that ingests Markdown knowledge docs, assists questionnaire design, analyzes returned survey sheets, and generates Markdown reports.

**Architecture:** Use a Python-first monolith so one engineer can ship quickly. FastAPI serves both HTTP endpoints and server-rendered pages, SQLite stores project metadata and run history, local folders store artifacts, and a retrieval + LLM layer enriches questionnaire drafting, text coding, and report writing without owning deterministic statistics.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLModel, Alembic, pandas, pytest, httpx/TestClient, ChromaDB (or equivalent local persistent vector store), a provider-agnostic LLM client adapter, uv for environment management.

---

## Assumptions

- This is a brand-new repo, so the plan includes project scaffolding.
- The first release is for one local user, so auth, multi-tenancy, and background workers stay out of scope.
- Knowledge source files are Markdown and may include YAML frontmatter.
- Survey uploads are CSV or Excel exports from questionnaire tools.
- The UI is intentionally thin: forms, lists, preview pages, and export actions are enough for MVP.

## Suggested Repository Layout

```text
docs/plans/
src/game_survey_workbench/
  app.py
  config.py
  db.py
  models/
  routes/
  services/
  llm/
  retrieval/
  templates/
  static/
tests/
workspace/
  knowledge/
  projects/
```

### Task 1: Bootstrap the Python application skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/game_survey_workbench/__init__.py`
- Create: `src/game_survey_workbench/app.py`
- Create: `src/game_survey_workbench/config.py`
- Create: `tests/test_app_smoke.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


def test_healthcheck_returns_ok():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_app_smoke.py -v`
Expected: FAIL with import or route errors because the app does not exist yet.

**Step 3: Write minimal implementation**

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_app_smoke.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml README.md src/game_survey_workbench/__init__.py src/game_survey_workbench/app.py src/game_survey_workbench/config.py tests/test_app_smoke.py
git commit -m "chore: bootstrap survey workbench app"
```

### Task 2: Add configuration, database bootstrapping, and workspace directories

**Files:**
- Create: `src/game_survey_workbench/db.py`
- Create: `src/game_survey_workbench/models/base.py`
- Create: `src/game_survey_workbench/services/workspace.py`
- Modify: `src/game_survey_workbench/app.py`
- Create: `tests/test_workspace_bootstrap.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from game_survey_workbench.services.workspace import bootstrap_workspace


def test_bootstrap_workspace_creates_expected_directories(tmp_path: Path):
    bootstrap_workspace(tmp_path)

    assert (tmp_path / "knowledge").exists()
    assert (tmp_path / "projects").exists()
    assert (tmp_path / "artifacts").exists()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workspace_bootstrap.py -v`
Expected: FAIL because the workspace service is missing.

**Step 3: Write minimal implementation**

```python
from pathlib import Path


def bootstrap_workspace(root: Path) -> None:
    for name in ("knowledge", "projects", "artifacts"):
        (root / name).mkdir(parents=True, exist_ok=True)
```

Also add a `get_engine()` helper in `db.py` and initialize workspace + metadata in FastAPI startup.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_workspace_bootstrap.py tests/test_app_smoke.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/db.py src/game_survey_workbench/models/base.py src/game_survey_workbench/services/workspace.py src/game_survey_workbench/app.py tests/test_workspace_bootstrap.py
git commit -m "feat: initialize workspace and database bootstrap"
```

### Task 3: Model knowledge documents and parse Markdown metadata

**Files:**
- Create: `src/game_survey_workbench/models/knowledge.py`
- Create: `src/game_survey_workbench/services/knowledge_parser.py`
- Create: `tests/test_knowledge_parser.py`

**Step 1: Write the failing test**

```python
from game_survey_workbench.services.knowledge_parser import parse_markdown_document


def test_parse_markdown_document_extracts_frontmatter_and_body():
    raw = """---
title: Retention Framework
doc_type: theory
stage:
  - analysis
tags:
  - retention
---
Body text here.
"""

    document = parse_markdown_document(raw)

    assert document.title == "Retention Framework"
    assert document.doc_type == "theory"
    assert document.stages == ["analysis"]
    assert document.body == "Body text here."
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_knowledge_parser.py -v`
Expected: FAIL because the parser module and document model are absent.

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass

import frontmatter


@dataclass
class ParsedKnowledgeDocument:
    title: str
    doc_type: str
    stages: list[str]
    body: str


def parse_markdown_document(raw: str) -> ParsedKnowledgeDocument:
    post = frontmatter.loads(raw)
    return ParsedKnowledgeDocument(
        title=post.get("title", "Untitled"),
        doc_type=post.get("doc_type", "experience"),
        stages=list(post.get("stage", [])),
        body=post.content.strip(),
    )
```

Add a SQLModel for persisted document metadata with fields for source path, type, stages, tags, scenario, and priority.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_knowledge_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/knowledge.py src/game_survey_workbench/services/knowledge_parser.py tests/test_knowledge_parser.py
git commit -m "feat: add markdown knowledge parser"
```

### Task 4: Build knowledge ingestion and retrieval services

**Files:**
- Create: `src/game_survey_workbench/retrieval/chunking.py`
- Create: `src/game_survey_workbench/retrieval/store.py`
- Create: `src/game_survey_workbench/services/knowledge_ingest.py`
- Create: `tests/test_knowledge_ingest.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file


def test_ingest_knowledge_file_returns_chunk_count(tmp_path: Path):
    source = tmp_path / "doc.md"
    source.write_text("# Title\n\nParagraph one.\n\nParagraph two.", encoding="utf-8")

    result = ingest_knowledge_file(source, project_root=tmp_path)

    assert result.document_title == "Title"
    assert result.chunk_count >= 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_knowledge_ingest.py -v`
Expected: FAIL because the ingestion pipeline is missing.

**Step 3: Write minimal implementation**

```python
def split_markdown(body: str, chunk_size: int = 800) -> list[str]:
    paragraphs = [item.strip() for item in body.split("\n\n") if item.strip()]
    return paragraphs or [body.strip()]
```

Implement:

- deterministic chunking that preserves headings
- metadata persistence in SQLite
- vector persistence in a local store directory
- a retrieval function that accepts `query`, `stages`, `doc_types`, and `scenarios`

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_knowledge_ingest.py tests/test_knowledge_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/retrieval/chunking.py src/game_survey_workbench/retrieval/store.py src/game_survey_workbench/services/knowledge_ingest.py tests/test_knowledge_ingest.py
git commit -m "feat: add knowledge ingestion pipeline"
```

### Task 5: Add project and knowledge-pack management

**Files:**
- Create: `src/game_survey_workbench/models/project.py`
- Create: `src/game_survey_workbench/services/projects.py`
- Create: `src/game_survey_workbench/routes/projects.py`
- Modify: `src/game_survey_workbench/app.py`
- Create: `tests/test_projects.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


def test_create_project_persists_selected_knowledge_filters():
    client = TestClient(create_app())

    response = client.post(
        "/projects",
        json={
            "slug": "new-player-onboarding",
            "name": "New Player Onboarding",
            "knowledge_pack": {
                "doc_types": ["theory", "industry"],
                "scenarios": ["onboarding"],
            },
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["slug"] == "new-player-onboarding"
    assert payload["knowledge_pack"]["scenarios"] == ["onboarding"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_projects.py -v`
Expected: FAIL because the route and model do not exist.

**Step 3: Write minimal implementation**

```python
class KnowledgePack(SQLModel):
    doc_types: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)


class ProjectCreate(SQLModel):
    slug: str
    name: str
    knowledge_pack: KnowledgePack
```

Implement a project service that:

- creates the project row
- creates `workspace/projects/<slug>/...` folders
- stores knowledge pack filters for later retrieval queries

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_projects.py tests/test_workspace_bootstrap.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/project.py src/game_survey_workbench/services/projects.py src/game_survey_workbench/routes/projects.py src/game_survey_workbench/app.py tests/test_projects.py
git commit -m "feat: add project and knowledge pack management"
```

### Task 6: Implement questionnaire spec storage and design-assistant prompt assembly

**Files:**
- Create: `src/game_survey_workbench/models/questionnaire.py`
- Create: `src/game_survey_workbench/llm/prompts/questionnaire_design.md`
- Create: `src/game_survey_workbench/services/questionnaires.py`
- Create: `src/game_survey_workbench/routes/questionnaires.py`
- Create: `tests/test_questionnaire_service.py`

**Step 1: Write the failing test**

```python
from game_survey_workbench.services.questionnaires import build_questionnaire_design_context


def test_design_context_uses_project_goal_and_retrieved_knowledge():
    context = build_questionnaire_design_context(
        project_name="Version Satisfaction",
        research_goal="Understand version acceptance drivers",
        hypotheses=["Combat pacing affects satisfaction"],
        knowledge_snippets=["Use behavior + attitude questions together."],
    )

    assert "Version Satisfaction" in context
    assert "Combat pacing affects satisfaction" in context
    assert "Use behavior + attitude questions together." in context
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_questionnaire_service.py -v`
Expected: FAIL because the questionnaire module is missing.

**Step 3: Write minimal implementation**

```python
def build_questionnaire_design_context(
    *,
    project_name: str,
    research_goal: str,
    hypotheses: list[str],
    knowledge_snippets: list[str],
) -> str:
    return "\n".join(
        [
            f"Project: {project_name}",
            f"Goal: {research_goal}",
            "Hypotheses:",
            *[f"- {item}" for item in hypotheses],
            "Knowledge:",
            *[f"- {item}" for item in knowledge_snippets],
        ]
    )
```

Implement storage for:

- questionnaire spec versions
- question definitions
- intended analysis purpose per question
- a route that requests a draft from the LLM adapter and saves the returned Markdown spec

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_questionnaire_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/questionnaire.py src/game_survey_workbench/llm/prompts/questionnaire_design.md src/game_survey_workbench/services/questionnaires.py src/game_survey_workbench/routes/questionnaires.py tests/test_questionnaire_service.py
git commit -m "feat: add questionnaire design workflow"
```

### Task 7: Implement survey upload, schema inference, and normalized dataset export

**Files:**
- Create: `src/game_survey_workbench/models/dataset.py`
- Create: `src/game_survey_workbench/services/dataset_import.py`
- Create: `src/game_survey_workbench/routes/datasets.py`
- Create: `tests/test_dataset_import.py`
- Create: `tests/fixtures/surveys/basic_survey.csv`

**Step 1: Write the failing test**

```python
from pathlib import Path

from game_survey_workbench.services.dataset_import import import_dataset


def test_import_dataset_identifies_other_text_columns(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "Q1,Q1_其他说明,Q2\n满意,节奏太慢,5\n",
        encoding="utf-8",
    )

    dataset = import_dataset(csv_path, project_slug="version-feedback", workspace_root=tmp_path)

    assert dataset.question_columns["Q1"].other_text_column == "Q1_其他说明"
    assert dataset.question_columns["Q2"].question_type == "scale"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dataset_import.py -v`
Expected: FAIL because the import pipeline does not exist.

**Step 3: Write minimal implementation**

```python
def detect_question_type(series: pd.Series) -> str:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().all():
        return "scale"
    return "single_choice"
```

Implement:

- CSV and Excel readers
- heuristics for single choice, multi select, scale, matrix, free text
- pairing logic for `其他`/`other` columns
- normalized JSON schema saved under `workspace/projects/<slug>/data/schema/`

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dataset_import.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/dataset.py src/game_survey_workbench/services/dataset_import.py src/game_survey_workbench/routes/datasets.py tests/test_dataset_import.py tests/fixtures/surveys/basic_survey.csv
git commit -m "feat: add survey dataset import pipeline"
```

### Task 8: Add deterministic survey analytics

**Files:**
- Create: `src/game_survey_workbench/services/analytics.py`
- Create: `src/game_survey_workbench/models/analysis.py`
- Create: `tests/test_analytics.py`

**Step 1: Write the failing test**

```python
import pandas as pd

from game_survey_workbench.services.analytics import summarize_scale_question


def test_summarize_scale_question_returns_mean_and_top_box():
    series = pd.Series([5, 4, 5, 3, 4])

    summary = summarize_scale_question(series, top_box_values={4, 5})

    assert summary.mean == 4.2
    assert summary.top_box_rate == 0.8
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_analytics.py -v`
Expected: FAIL because analytics functions are missing.

**Step 3: Write minimal implementation**

```python
def summarize_scale_question(series, top_box_values: set[int]):
    clean = series.dropna().astype(float)
    return ScaleSummary(
        mean=round(float(clean.mean()), 3),
        top_box_rate=round(float(clean.isin(top_box_values).mean()), 3),
    )
```

Extend the service for:

- single-choice counts and percentages
- multi-select expansion
- matrix row summaries
- cross-tab summaries based on selected segment columns

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_analytics.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/analytics.py src/game_survey_workbench/models/analysis.py tests/test_analytics.py
git commit -m "feat: add deterministic analytics summaries"
```

### Task 9: Add LLM orchestration for text coding and insight synthesis

**Files:**
- Create: `src/game_survey_workbench/llm/client.py`
- Create: `src/game_survey_workbench/llm/prompts/open_text_coding.md`
- Create: `src/game_survey_workbench/llm/prompts/insight_synthesis.md`
- Create: `src/game_survey_workbench/services/insights.py`
- Create: `tests/test_insights_service.py`

**Step 1: Write the failing test**

```python
from game_survey_workbench.services.insights import build_insight_context


def test_build_insight_context_includes_stats_and_knowledge():
    context = build_insight_context(
        research_goal="Evaluate event satisfaction",
        statistical_findings=["Q3 top box dropped to 32%"],
        coded_themes=["Rewards feel too random"],
        knowledge_snippets=["Perceived fairness strongly affects repeat engagement."],
    )

    assert "Q3 top box dropped to 32%" in context
    assert "Rewards feel too random" in context
    assert "Perceived fairness strongly affects repeat engagement." in context
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_insights_service.py -v`
Expected: FAIL because insight orchestration is missing.

**Step 3: Write minimal implementation**

```python
def build_insight_context(
    *,
    research_goal: str,
    statistical_findings: list[str],
    coded_themes: list[str],
    knowledge_snippets: list[str],
) -> str:
    sections = [
        f"Goal: {research_goal}",
        "Stats:",
        *[f"- {item}" for item in statistical_findings],
        "Themes:",
        *[f"- {item}" for item in coded_themes],
        "Knowledge:",
        *[f"- {item}" for item in knowledge_snippets],
    ]
    return "\n".join(sections)
```

Implement:

- an LLM adapter interface with a fake client for tests
- open-text coding request/response models
- insight synthesis that takes deterministic analytics as input and returns cited narrative blocks

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_insights_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/llm/client.py src/game_survey_workbench/llm/prompts/open_text_coding.md src/game_survey_workbench/llm/prompts/insight_synthesis.md src/game_survey_workbench/services/insights.py tests/test_insights_service.py
git commit -m "feat: add insight synthesis workflow"
```

### Task 10: Generate versioned Markdown reports

**Files:**
- Create: `src/game_survey_workbench/services/reporting.py`
- Create: `src/game_survey_workbench/templates/reports/report.md.j2`
- Create: `src/game_survey_workbench/routes/reports.py`
- Create: `tests/test_reporting.py`

**Step 1: Write the failing test**

```python
from game_survey_workbench.services.reporting import render_report_markdown


def test_render_report_markdown_includes_required_sections():
    markdown = render_report_markdown(
        title="Version Satisfaction Report",
        summary_points=["Combat satisfaction is declining."],
        sections={"Key Findings": ["Top box fell among long-term payers."]},
    )

    assert "# Version Satisfaction Report" in markdown
    assert "## Key Findings" in markdown
    assert "Combat satisfaction is declining." in markdown
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reporting.py -v`
Expected: FAIL because the reporting module and template do not exist.

**Step 3: Write minimal implementation**

```python
from jinja2 import Environment, PackageLoader, select_autoescape


def render_report_markdown(title: str, summary_points: list[str], sections: dict[str, list[str]]) -> str:
    template = get_environment().get_template("reports/report.md.j2")
    return template.render(title=title, summary_points=summary_points, sections=sections)
```

Implement versioned saves to `workspace/projects/<slug>/reports/report-YYYY-MM-DD-HHMM.md` and store linked analysis run IDs in SQLite.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_reporting.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/reporting.py src/game_survey_workbench/templates/reports/report.md.j2 src/game_survey_workbench/routes/reports.py tests/test_reporting.py
git commit -m "feat: add markdown report generation"
```

### Task 11: Add the local web UI for the three entry points

**Files:**
- Create: `src/game_survey_workbench/templates/layout.html`
- Create: `src/game_survey_workbench/templates/index.html`
- Create: `src/game_survey_workbench/templates/projects/detail.html`
- Create: `src/game_survey_workbench/templates/questionnaires/detail.html`
- Create: `src/game_survey_workbench/templates/analysis/detail.html`
- Create: `src/game_survey_workbench/static/app.css`
- Modify: `src/game_survey_workbench/routes/projects.py`
- Modify: `src/game_survey_workbench/routes/questionnaires.py`
- Modify: `src/game_survey_workbench/routes/datasets.py`
- Modify: `src/game_survey_workbench/routes/reports.py`
- Create: `tests/test_html_routes.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


def test_homepage_lists_three_primary_workflows():
    client = TestClient(create_app())

    response = client.get("/")

    body = response.text
    assert response.status_code == 200
    assert "问卷设计" in body
    assert "数据分析" in body
    assert "报告生成" in body
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_html_routes.py -v`
Expected: FAIL because the HTML routes and templates are absent.

**Step 3: Write minimal implementation**

```python
@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"workflows": ["问卷设计", "数据分析", "报告生成"]},
    )
```

Implement simple pages for:

- project creation
- knowledge upload trigger
- questionnaire draft preview
- dataset import status
- analysis run detail
- report export action

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_html_routes.py tests/test_app_smoke.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/templates/layout.html src/game_survey_workbench/templates/index.html src/game_survey_workbench/templates/projects/detail.html src/game_survey_workbench/templates/questionnaires/detail.html src/game_survey_workbench/templates/analysis/detail.html src/game_survey_workbench/static/app.css src/game_survey_workbench/routes/projects.py src/game_survey_workbench/routes/questionnaires.py src/game_survey_workbench/routes/datasets.py src/game_survey_workbench/routes/reports.py tests/test_html_routes.py
git commit -m "feat: add local workbench interface"
```

### Task 12: Add end-to-end smoke coverage and seed content

**Files:**
- Create: `tests/test_end_to_end_smoke.py`
- Create: `tests/fixtures/knowledge/retention_framework.md`
- Create: `tests/fixtures/knowledge/version_feedback.md`
- Create: `scripts/seed_demo_workspace.py`
- Modify: `README.md`

**Step 1: Write the failing test**

```python
def test_end_to_end_flow_creates_report(client, seeded_workspace):
    project = client.post("/projects", json={"slug": "demo", "name": "Demo", "knowledge_pack": {}}).json()
    draft = client.post(f"/projects/{project['slug']}/questionnaires/draft", json={"research_goal": "Learn why players drop after the patch"}).json()
    dataset = client.post(f"/projects/{project['slug']}/datasets/import").json()
    report = client.post(f"/projects/{project['slug']}/reports/generate", json={"analysis_run_id": dataset["analysis_run_id"]}).json()

    assert draft["version_id"]
    assert dataset["dataset_id"]
    assert report["path"].endswith(".md")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_end_to_end_smoke.py -v`
Expected: FAIL because the full route chain and fixtures are not wired together yet.

**Step 3: Write minimal implementation**

```python
@pytest.fixture()
def seeded_workspace(tmp_path):
    bootstrap_workspace(tmp_path)
    shutil.copytree(FIXTURES / "knowledge", tmp_path / "knowledge", dirs_exist_ok=True)
    return tmp_path
```

Wire the smoke test through the fake LLM adapter so CI does not depend on external APIs.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_end_to_end_smoke.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_end_to_end_smoke.py tests/fixtures/knowledge/retention_framework.md tests/fixtures/knowledge/version_feedback.md scripts/seed_demo_workspace.py README.md
git commit -m "test: add end-to-end smoke coverage"
```

## Verification Checklist Before Any Implementation Claim

- Run: `uv run pytest -v`
- Run: `uv run python -m compileall src`
- Start the app locally and confirm:
  - `/health` returns `{"status": "ok"}`
  - homepage exposes the three workflows
  - a seeded project can generate a Markdown report

## Risks and Notes

- If ChromaDB or the chosen vector store proves unstable on the target Windows environment, replace it with a simple persisted embedding table plus cosine search before expanding the scope.
- Keep the LLM client behind an interface from day one so tests can use a fake client and implementation can swap providers later.
- Do not let report generation calculate statistics on its own; it must consume saved analysis outputs.
- Do not ingest the whole knowledge base for every prompt. Always filter through the project’s knowledge pack first.
- Favor UTF-8 throughout because question text and report content will include Chinese.
