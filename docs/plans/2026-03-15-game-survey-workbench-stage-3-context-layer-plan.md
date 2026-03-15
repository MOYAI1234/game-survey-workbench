# Stage 3: Workbench Context Layer — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give projects a persistent Research Brief and Task Plan so that project context carries across questionnaire design, analysis, and report generation — turning the project from a thin namespace into the central truth source for every downstream workflow.

**Architecture:** Extend `ProjectRecord` with a `description` field and add two new models — `ResearchBrief` (one per project, editable) and `TaskPlan` (derived checklist). Build a project homepage that shows brief, plan, and links to existing workflows. Reshape the workbench landing page to list real projects instead of a static workflow menu. All changes are backend-model and template-level; no new JS framework, no new LLM prompts yet.

**Tech Stack:** SQLModel / SQLAlchemy (existing), FastAPI routes (existing), Jinja2 templates (existing), pytest with real-sample fixtures (existing pattern)

**North-star alignment:** This plan implements Stage 3 scope from the north-star document — "lightweight project kickoff page, Research Brief as project truth source, Task Plan derived from Research Brief, clearer project homepage and workflow guidance." It does not change the core product loop or introduce new LLM features.

**Relationship to Stage 2 follow-ups:** Any remaining Stage 2 shell-polish items (report executive summary, harness alignment) stay in the follow-up backlog and are not addressed here.

---

## Scope summary

| Sub-stage | What it delivers |
|-----------|-----------------|
| 3A | Project model enrichment — `description`, `status`, `updated_at` |
| 3B | Research Brief model and CRUD |
| 3C | Task Plan model and CRUD |
| 3D | Project homepage template — brief, plan, workflow links |
| 3E | Workbench landing page — real project listing |
| 3F | Context injection — feed brief into questionnaire and insight prompts |

Each sub-stage is independently shippable and testable.

---

## Task 1: Enrich ProjectRecord (Stage 3A)

**Files:**
- Modify: `src/game_survey_workbench/models/project.py`
- Modify: `src/game_survey_workbench/services/projects.py`
- Modify: `src/game_survey_workbench/routes/projects.py`
- Create: `tests/test_stage3a_project_enrichment.py`

### Step 1: Write the failing test

```python
# tests/test_stage3a_project_enrichment.py
from pathlib import Path
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project, get_project, list_projects


def test_create_project_with_description(tmp_path: Path):
    payload = ProjectCreate(
        slug="season-pass-v2",
        name="Season Pass V2 Research",
        description="Evaluate player retention impact of the redesigned season pass.",
    )
    record = create_project(payload, workspace_root=tmp_path)
    assert record.description == payload.description
    assert record.status == "active"
    assert record.updated_at is not None


def test_list_projects_returns_all(tmp_path: Path):
    for i in range(3):
        create_project(
            ProjectCreate(slug=f"proj-{i}", name=f"Project {i}"),
            workspace_root=tmp_path,
        )
    projects = list_projects(workspace_root=tmp_path)
    assert len(projects) == 3
    slugs = [p.slug for p in projects]
    assert "proj-0" in slugs and "proj-2" in slugs


def test_project_description_defaults_to_empty(tmp_path: Path):
    payload = ProjectCreate(slug="minimal", name="Minimal")
    record = create_project(payload, workspace_root=tmp_path)
    assert record.description == ""
```

### Step 2: Run test to verify it fails

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage3a_project_enrichment.py -v`
Expected: FAIL — `description` field does not exist on `ProjectCreate`, `list_projects` does not exist.

### Step 3: Implement model and service changes

In `src/game_survey_workbench/models/project.py`, add `description`, `status`, and `updated_at` to both `ProjectCreate` and `ProjectRecord`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class KnowledgePack(SQLModel):
    doc_types: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)


class ProjectCreate(SQLModel):
    slug: str
    name: str
    description: str = ""
    knowledge_pack: KnowledgePack = Field(default_factory=KnowledgePack)


class ProjectRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str
    description: str = ""
    status: str = "active"
    knowledge_pack: dict = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

In `src/game_survey_workbench/services/projects.py`, add `list_projects`:

```python
def list_projects(*, workspace_root: Path) -> list[ProjectRecord]:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        return list(session.exec(select(ProjectRecord)).all())
```

And update `create_project` to pass `description` through:

```python
record = ProjectRecord(
    slug=payload.slug,
    name=payload.name,
    description=payload.description,
    knowledge_pack=payload.knowledge_pack.model_dump(),
)
```

### Step 4: Run test to verify it passes

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage3a_project_enrichment.py -v`
Expected: 3 passed

### Step 5: Run full regression

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 89+ passed, 0 failed (existing tests should not break because `description` defaults to `""`)

### Step 6: Commit

```bash
git add tests/test_stage3a_project_enrichment.py src/game_survey_workbench/models/project.py src/game_survey_workbench/services/projects.py
git commit -m "feat(stage3a): enrich ProjectRecord with description, status, updated_at; add list_projects"
```

---

## Task 2: Research Brief model and CRUD (Stage 3B)

**Files:**
- Create: `src/game_survey_workbench/models/research_brief.py`
- Create: `src/game_survey_workbench/services/research_brief.py`
- Modify: `src/game_survey_workbench/routes/projects.py`
- Create: `tests/test_stage3b_research_brief.py`

### Step 1: Write the failing test

```python
# tests/test_stage3b_research_brief.py
from pathlib import Path
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.research_brief import ResearchBriefPayload
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.research_brief import (
    save_research_brief,
    get_research_brief,
)


def _setup_project(tmp_path: Path) -> str:
    create_project(
        ProjectCreate(slug="bp-study", name="Battle Pass Study"),
        workspace_root=tmp_path,
    )
    return "bp-study"


def test_save_and_retrieve_brief(tmp_path: Path):
    slug = _setup_project(tmp_path)
    payload = ResearchBriefPayload(
        background="Season pass conversion dropped 12% MoM.",
        objectives=["Identify friction points in pass purchase flow",
                     "Measure perceived value of pass rewards"],
        hypotheses=["Players find the reward preview unclear",
                     "Price anchor is missing after tutorial"],
        target_audience="Active players L7 >= 3 days, non-payers",
        success_criteria="Actionable redesign brief for product team",
    )
    brief = save_research_brief(
        project_slug=slug, payload=payload, workspace_root=tmp_path,
    )
    assert brief.project_slug == slug
    assert brief.background == payload.background
    assert len(brief.objectives) == 2

    loaded = get_research_brief(project_slug=slug, workspace_root=tmp_path)
    assert loaded is not None
    assert loaded.id == brief.id


def test_save_brief_overwrites_previous(tmp_path: Path):
    slug = _setup_project(tmp_path)
    v1 = ResearchBriefPayload(
        background="V1 background",
        objectives=["obj1"],
    )
    save_research_brief(project_slug=slug, payload=v1, workspace_root=tmp_path)

    v2 = ResearchBriefPayload(
        background="V2 background",
        objectives=["obj1", "obj2"],
    )
    save_research_brief(project_slug=slug, payload=v2, workspace_root=tmp_path)

    loaded = get_research_brief(project_slug=slug, workspace_root=tmp_path)
    assert loaded is not None
    assert loaded.background == "V2 background"
    assert len(loaded.objectives) == 2


def test_get_brief_returns_none_when_missing(tmp_path: Path):
    slug = _setup_project(tmp_path)
    assert get_research_brief(project_slug=slug, workspace_root=tmp_path) is None
```

### Step 2: Run test to verify it fails

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage3b_research_brief.py -v`
Expected: FAIL — modules do not exist yet.

### Step 3: Implement model

```python
# src/game_survey_workbench/models/research_brief.py
from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class ResearchBriefPayload(SQLModel):
    background: str = ""
    objectives: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    target_audience: str = ""
    success_criteria: str = ""


class ResearchBriefRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_slug: str = Field(index=True, unique=True)
    background: str = ""
    objectives: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    hypotheses: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    target_audience: str = ""
    success_criteria: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

### Step 4: Implement service

```python
# src/game_survey_workbench/services/research_brief.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.research_brief import (
    ResearchBriefPayload,
    ResearchBriefRecord,
)


def save_research_brief(
    *,
    project_slug: str,
    payload: ResearchBriefPayload,
    workspace_root: Path,
) -> ResearchBriefRecord:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        existing = session.exec(
            select(ResearchBriefRecord).where(
                ResearchBriefRecord.project_slug == project_slug
            )
        ).first()
        if existing is not None:
            existing.background = payload.background
            existing.objectives = payload.objectives
            existing.hypotheses = payload.hypotheses
            existing.target_audience = payload.target_audience
            existing.success_criteria = payload.success_criteria
            existing.updated_at = datetime.now(UTC)
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing

        record = ResearchBriefRecord(
            project_slug=project_slug,
            background=payload.background,
            objectives=payload.objectives,
            hypotheses=payload.hypotheses,
            target_audience=payload.target_audience,
            success_criteria=payload.success_criteria,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def get_research_brief(
    *, project_slug: str, workspace_root: Path
) -> ResearchBriefRecord | None:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        return session.exec(
            select(ResearchBriefRecord).where(
                ResearchBriefRecord.project_slug == project_slug
            )
        ).first()
```

### Step 5: Register model in db.py

Wherever `create_db_and_tables` calls `SQLModel.metadata.create_all`, ensure `ResearchBriefRecord` is imported so its table is created. Check existing pattern in `src/game_survey_workbench/db.py` — add the import alongside other model imports.

### Step 6: Run test to verify it passes

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage3b_research_brief.py -v`
Expected: 3 passed

### Step 7: Add API routes

In `src/game_survey_workbench/routes/projects.py`, add PUT and GET endpoints for the brief:

```python
from game_survey_workbench.models.research_brief import ResearchBriefPayload
from game_survey_workbench.services.research_brief import (
    save_research_brief,
    get_research_brief,
)

@router.put("/projects/{project_slug}/brief")
def upsert_brief(project_slug: str, payload: ResearchBriefPayload):
    settings = get_settings()
    brief = save_research_brief(
        project_slug=project_slug,
        payload=payload,
        workspace_root=settings.workspace_root,
    )
    return {
        "project_slug": brief.project_slug,
        "background": brief.background,
        "objectives": brief.objectives,
        "hypotheses": brief.hypotheses,
        "target_audience": brief.target_audience,
        "success_criteria": brief.success_criteria,
    }

@router.get("/projects/{project_slug}/brief")
def read_brief(project_slug: str):
    settings = get_settings()
    brief = get_research_brief(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    if brief is None:
        return {"project_slug": project_slug, "brief": None}
    return {
        "project_slug": brief.project_slug,
        "background": brief.background,
        "objectives": brief.objectives,
        "hypotheses": brief.hypotheses,
        "target_audience": brief.target_audience,
        "success_criteria": brief.success_criteria,
    }
```

### Step 8: Run full regression

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: all previous tests + 3 new pass

### Step 9: Commit

```bash
git add src/game_survey_workbench/models/research_brief.py src/game_survey_workbench/services/research_brief.py src/game_survey_workbench/routes/projects.py src/game_survey_workbench/db.py tests/test_stage3b_research_brief.py
git commit -m "feat(stage3b): add ResearchBrief model, CRUD service, and API routes"
```

---

## Task 3: Task Plan model and CRUD (Stage 3C)

**Files:**
- Create: `src/game_survey_workbench/models/task_plan.py`
- Create: `src/game_survey_workbench/services/task_plan.py`
- Modify: `src/game_survey_workbench/routes/projects.py`
- Create: `tests/test_stage3c_task_plan.py`

### Step 1: Write the failing test

```python
# tests/test_stage3c_task_plan.py
from pathlib import Path
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.task_plan import TaskPlanPayload, TaskItem
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.task_plan import save_task_plan, get_task_plan


def _setup(tmp_path: Path) -> str:
    create_project(
        ProjectCreate(slug="bp-study", name="BP Study"),
        workspace_root=tmp_path,
    )
    return "bp-study"


def test_save_and_load_plan(tmp_path: Path):
    slug = _setup(tmp_path)
    payload = TaskPlanPayload(tasks=[
        TaskItem(label="Ingest knowledge docs", status="done"),
        TaskItem(label="Design questionnaire", status="pending"),
        TaskItem(label="Collect responses", status="pending"),
        TaskItem(label="Run analysis", status="pending"),
        TaskItem(label="Generate report", status="pending"),
    ])
    plan = save_task_plan(project_slug=slug, payload=payload, workspace_root=tmp_path)
    assert plan.project_slug == slug
    assert len(plan.tasks) == 5
    assert plan.tasks[0]["status"] == "done"

    loaded = get_task_plan(project_slug=slug, workspace_root=tmp_path)
    assert loaded is not None
    assert len(loaded.tasks) == 5


def test_save_plan_overwrites(tmp_path: Path):
    slug = _setup(tmp_path)
    v1 = TaskPlanPayload(tasks=[TaskItem(label="Step A")])
    save_task_plan(project_slug=slug, payload=v1, workspace_root=tmp_path)

    v2 = TaskPlanPayload(tasks=[TaskItem(label="Step A", status="done"),
                                 TaskItem(label="Step B")])
    save_task_plan(project_slug=slug, payload=v2, workspace_root=tmp_path)

    loaded = get_task_plan(project_slug=slug, workspace_root=tmp_path)
    assert loaded is not None
    assert len(loaded.tasks) == 2


def test_get_plan_returns_none_when_missing(tmp_path: Path):
    slug = _setup(tmp_path)
    assert get_task_plan(project_slug=slug, workspace_root=tmp_path) is None
```

### Step 2: Run test to verify it fails

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage3c_task_plan.py -v`
Expected: FAIL — modules do not exist.

### Step 3: Implement model

```python
# src/game_survey_workbench/models/task_plan.py
from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class TaskItem(SQLModel):
    label: str
    status: str = "pending"


class TaskPlanPayload(SQLModel):
    tasks: list[TaskItem] = Field(default_factory=list)


class TaskPlanRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_slug: str = Field(index=True, unique=True)
    tasks: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

### Step 4: Implement service

```python
# src/game_survey_workbench/services/task_plan.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.task_plan import (
    TaskPlanPayload,
    TaskPlanRecord,
)


def save_task_plan(
    *,
    project_slug: str,
    payload: TaskPlanPayload,
    workspace_root: Path,
) -> TaskPlanRecord:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    tasks_data = [t.model_dump() for t in payload.tasks]
    with Session(engine) as session:
        existing = session.exec(
            select(TaskPlanRecord).where(
                TaskPlanRecord.project_slug == project_slug
            )
        ).first()
        if existing is not None:
            existing.tasks = tasks_data
            existing.updated_at = datetime.now(UTC)
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing

        record = TaskPlanRecord(
            project_slug=project_slug,
            tasks=tasks_data,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def get_task_plan(
    *, project_slug: str, workspace_root: Path,
) -> TaskPlanRecord | None:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        return session.exec(
            select(TaskPlanRecord).where(
                TaskPlanRecord.project_slug == project_slug
            )
        ).first()
```

### Step 5: Register in db.py, add routes

Same pattern as Task 2: import `TaskPlanRecord` in `db.py`, add `PUT /projects/{slug}/plan` and `GET /projects/{slug}/plan` in `routes/projects.py`.

### Step 6: Run tests

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage3c_task_plan.py -v`
Expected: 3 passed

### Step 7: Full regression

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: all pass

### Step 8: Commit

```bash
git add src/game_survey_workbench/models/task_plan.py src/game_survey_workbench/services/task_plan.py src/game_survey_workbench/routes/projects.py src/game_survey_workbench/db.py tests/test_stage3c_task_plan.py
git commit -m "feat(stage3c): add TaskPlan model, CRUD service, and API routes"
```

---

## Task 4: Project homepage template (Stage 3D)

**Files:**
- Modify: `src/game_survey_workbench/routes/projects.py`
- Modify: `src/game_survey_workbench/templates/projects/detail.html`
- Create: `tests/test_stage3d_project_homepage.py`

### Step 1: Write the failing test

```python
# tests/test_stage3d_project_homepage.py
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app(workspace_root=tmp_path)
    return TestClient(app)


def test_project_homepage_shows_brief_section(client: TestClient, tmp_path: Path):
    create_project(
        ProjectCreate(slug="bp", name="Battle Pass", description="Pass study"),
        workspace_root=tmp_path,
    )
    response = client.get("/projects/bp")
    assert response.status_code == 200
    html = response.text
    assert "Battle Pass" in html
    assert "Pass study" in html
    assert "Research Brief" in html or "研究简报" in html
    assert "Task Plan" in html or "任务计划" in html
    assert "问卷设计" in html
    assert "数据分析" in html
    assert "报告生成" in html
```

### Step 2: Run test to verify it fails

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage3d_project_homepage.py -v`
Expected: FAIL — current detail template does not show brief/plan/workflow links.

### Step 3: Update route to pass context

In `routes/projects.py`, update `project_detail` to load the project, brief, and plan:

```python
from game_survey_workbench.services.projects import create_project, get_project, list_projects
from game_survey_workbench.services.research_brief import get_research_brief
from game_survey_workbench.services.task_plan import get_task_plan

@router.get("/projects/{project_slug}", response_class=HTMLResponse)
def project_detail(project_slug: str, request: Request):
    settings = get_settings()
    project = get_project(workspace_root=settings.workspace_root, project_slug=project_slug)
    brief = get_research_brief(project_slug=project_slug, workspace_root=settings.workspace_root)
    plan = get_task_plan(project_slug=project_slug, workspace_root=settings.workspace_root)
    return templates.TemplateResponse(
        request,
        "projects/detail.html",
        {
            "project": project,
            "project_slug": project_slug,
            "brief": brief,
            "plan": plan,
        },
    )
```

### Step 4: Update template

Replace `src/game_survey_workbench/templates/projects/detail.html`:

```html
{% extends "layout.html" %}
{% block title %}{{ project.name if project else project_slug }}{% endblock %}
{% block content %}
<header>
  <h1>{{ project.name if project else project_slug }}</h1>
  {% if project and project.description %}
  <p class="project-description">{{ project.description }}</p>
  {% endif %}
  {% if project and project.status %}
  <span class="status-badge">{{ project.status }}</span>
  {% endif %}
</header>

<section class="brief-section">
  <h2>Research Brief / 研究简报</h2>
  {% if brief %}
  <dl>
    <dt>Background</dt><dd>{{ brief.background }}</dd>
    <dt>Objectives</dt>
    <dd><ul>{% for obj in brief.objectives %}<li>{{ obj }}</li>{% endfor %}</ul></dd>
    {% if brief.hypotheses %}
    <dt>Hypotheses</dt>
    <dd><ul>{% for h in brief.hypotheses %}<li>{{ h }}</li>{% endfor %}</ul></dd>
    {% endif %}
    {% if brief.target_audience %}
    <dt>Target Audience</dt><dd>{{ brief.target_audience }}</dd>
    {% endif %}
    {% if brief.success_criteria %}
    <dt>Success Criteria</dt><dd>{{ brief.success_criteria }}</dd>
    {% endif %}
  </dl>
  {% else %}
  <p class="empty-state">No brief yet. Use <code>PUT /projects/{{ project_slug }}/brief</code> to set one.</p>
  {% endif %}
</section>

<section class="plan-section">
  <h2>Task Plan / 任务计划</h2>
  {% if plan and plan.tasks %}
  <ul class="task-list">
    {% for task in plan.tasks %}
    <li class="task-{{ task.status }}">
      {% if task.status == 'done' %}✓{% else %}○{% endif %}
      {{ task.label }}
    </li>
    {% endfor %}
  </ul>
  {% else %}
  <p class="empty-state">No task plan yet. Use <code>PUT /projects/{{ project_slug }}/plan</code> to set one.</p>
  {% endif %}
</section>

<section class="workflow-links">
  <h2>Workflows</h2>
  <ul>
    <li><a href="/projects/{{ project_slug }}/questionnaire">问卷设计</a></li>
    <li><a href="/projects/{{ project_slug }}/analysis">数据分析</a></li>
    <li><a href="/projects/{{ project_slug }}/reports">报告生成</a></li>
  </ul>
</section>
{% endblock %}
```

### Step 5: Run test

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage3d_project_homepage.py -v`
Expected: PASS

### Step 6: Full regression

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: all pass

### Step 7: Commit

```bash
git add src/game_survey_workbench/routes/projects.py src/game_survey_workbench/templates/projects/detail.html tests/test_stage3d_project_homepage.py
git commit -m "feat(stage3d): project homepage shows brief, task plan, and workflow links"
```

---

## Task 5: Workbench landing page with project list (Stage 3E)

**Files:**
- Modify: `src/game_survey_workbench/routes/ui.py`
- Modify: `src/game_survey_workbench/templates/index.html`
- Create: `tests/test_stage3e_landing_page.py`

### Step 1: Write the failing test

```python
# tests/test_stage3e_landing_page.py
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app(workspace_root=tmp_path)
    return TestClient(app)


def test_landing_page_lists_projects(client: TestClient, tmp_path: Path):
    create_project(ProjectCreate(slug="alpha", name="Alpha Study"), workspace_root=tmp_path)
    create_project(ProjectCreate(slug="beta", name="Beta Study"), workspace_root=tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "Alpha Study" in html
    assert "Beta Study" in html
    assert "/projects/alpha" in html
    assert "/projects/beta" in html


def test_landing_page_empty_state(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "No projects yet" in html or "暂无项目" in html
```

### Step 2: Run test to verify it fails

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage3e_landing_page.py -v`
Expected: FAIL — landing page shows static workflow list, not project list.

### Step 3: Update route and template

In `routes/ui.py`:

```python
from game_survey_workbench.config import get_settings
from game_survey_workbench.services.projects import list_projects

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    settings = get_settings()
    projects = list_projects(workspace_root=settings.workspace_root)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "projects": projects,
            "workflows": ["问卷设计", "数据分析", "报告生成"],
        },
    )
```

Update `templates/index.html`:

```html
{% extends "layout.html" %}
{% block title %}Game Survey Workbench{% endblock %}
{% block content %}
<section class="hero">
  <p class="eyebrow">Knowledge-Driven Research</p>
  <h1>Game Survey Workbench</h1>
  <p>围绕项目上下文统一管理问卷设计、数据分析与报告生成。</p>
</section>

<section class="project-list">
  <h2>Projects</h2>
  {% if projects %}
  <ul>
    {% for project in projects %}
    <li>
      <a href="/projects/{{ project.slug }}">{{ project.name }}</a>
      {% if project.description %}
      <span class="project-desc">— {{ project.description }}</span>
      {% endif %}
      <span class="status-badge">{{ project.status }}</span>
    </li>
    {% endfor %}
  </ul>
  {% else %}
  <p class="empty-state">暂无项目。Use <code>POST /projects</code> to create one.</p>
  {% endif %}
</section>

<section class="workflow-overview">
  <h3>Core Workflows</h3>
  <ul class="workflow-list">
    {% for workflow in workflows %}
    <li>{{ workflow }}</li>
    {% endfor %}
  </ul>
</section>
{% endblock %}
```

### Step 4: Run tests

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage3e_landing_page.py -v`
Expected: 2 passed

### Step 5: Full regression

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: all pass

### Step 6: Commit

```bash
git add src/game_survey_workbench/routes/ui.py src/game_survey_workbench/templates/index.html tests/test_stage3e_landing_page.py
git commit -m "feat(stage3e): landing page lists real projects with links"
```

---

## Task 6: Context injection — feed brief into downstream prompts (Stage 3F)

**Files:**
- Modify: `src/game_survey_workbench/services/questionnaires.py`
- Modify: `src/game_survey_workbench/services/insights.py`
- Create: `tests/test_stage3f_context_injection.py`

### Step 1: Write the failing test

```python
# tests/test_stage3f_context_injection.py
from game_survey_workbench.services.questionnaires import build_questionnaire_design_context


def test_context_includes_brief_fields():
    context = build_questionnaire_design_context(
        project_name="BP Study",
        research_goal="Measure pass purchase friction",
        hypotheses=["Reward preview is unclear"],
        knowledge_snippets=["Live-ops survey best practices"],
        brief_background="Conversion dropped 12% MoM",
        brief_target_audience="Active L7 >= 3 days, non-payers",
    )
    assert "Conversion dropped 12% MoM" in context
    assert "Active L7 >= 3 days, non-payers" in context


def test_context_works_without_brief():
    context = build_questionnaire_design_context(
        project_name="BP Study",
        research_goal="Measure pass purchase friction",
        hypotheses=["Reward preview is unclear"],
        knowledge_snippets=["Live-ops survey best practices"],
    )
    assert "BP Study" in context
    assert "Measure pass purchase friction" in context
    # No crash when brief fields are omitted
```

### Step 2: Run test to verify it fails

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage3f_context_injection.py -v`
Expected: FAIL — `build_questionnaire_design_context` does not accept `brief_background` or `brief_target_audience`.

### Step 3: Extend context builder

In `services/questionnaires.py`, add optional brief fields to `build_questionnaire_design_context`:

```python
def build_questionnaire_design_context(
    *,
    project_name: str,
    research_goal: str,
    hypotheses: list[str],
    knowledge_snippets: list[str | dict],
    brief_background: str = "",
    brief_target_audience: str = "",
) -> str:
    parts = [
        f"Project: {project_name}",
        f"Goal: {research_goal}",
    ]
    if brief_background:
        parts.append(f"Background: {brief_background}")
    if brief_target_audience:
        parts.append(f"Target Audience: {brief_target_audience}")
    parts.append("Hypotheses:")
    parts.extend(f"- {item}" for item in hypotheses)
    parts.append("Knowledge:")
    parts.extend(f"- {format_knowledge_item(item)}" for item in knowledge_snippets)
    return "\n".join(parts)
```

Update `generate_questionnaire_draft` to load the brief and pass it through:

```python
from game_survey_workbench.services.research_brief import get_research_brief

def generate_questionnaire_draft(...):
    # ... existing project + retrieval logic ...
    brief = get_research_brief(project_slug=project_slug, workspace_root=workspace_root)
    context = build_questionnaire_design_context(
        project_name=project.name,
        research_goal=payload.research_goal,
        hypotheses=payload.hypotheses,
        knowledge_snippets=snippets,
        brief_background=brief.background if brief else "",
        brief_target_audience=brief.target_audience if brief else "",
    )
    # ... rest unchanged ...
```

Apply a similar pattern to the insight synthesis service — load the brief and include its objectives in the insight context assembly. The exact insertion point depends on the current shape of `services/insights.py`; the pattern is the same: load brief, append relevant fields to the context string.

### Step 4: Run tests

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage3f_context_injection.py -v`
Expected: 2 passed

### Step 5: Full regression

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: all pass (existing questionnaire and insight tests should still pass because the new parameters default to `""`)

### Step 6: Commit

```bash
git add src/game_survey_workbench/services/questionnaires.py src/game_survey_workbench/services/insights.py tests/test_stage3f_context_injection.py
git commit -m "feat(stage3f): inject research brief context into questionnaire and insight prompts"
```

---

## Task 7: Update north-star document

**Files:**
- Modify: `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`

### Step 1: Update current stage status

Add a Stage 3 status entry in the "Current Stage Status" section:

```markdown
- Stage 3A `Project Model Enrichment`: not started
- Stage 3B `Research Brief Model and CRUD`: not started
- Stage 3C `Task Plan Model and CRUD`: not started
- Stage 3D `Project Homepage`: not started
- Stage 3E `Landing Page Project Listing`: not started
- Stage 3F `Context Injection`: not started
```

### Step 2: Update "Next Planned Artifact"

Change to indicate that Stage 3 planning is complete and execution can begin.

### Step 3: Commit

```bash
git add docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md
git commit -m "docs: update north-star with Stage 3 sub-stage breakdown"
```

---

## Acceptance criteria

Stage 3 is complete when:

1. `ProjectRecord` has `description`, `status`, and `updated_at` fields
2. `ResearchBriefRecord` exists with full CRUD and upsert semantics
3. `TaskPlanRecord` exists with full CRUD and upsert semantics
4. Project homepage (`/projects/{slug}`) renders brief, plan, and workflow links
5. Landing page (`/`) lists real projects from the database
6. `build_questionnaire_design_context` accepts and renders brief fields
7. Insight synthesis context includes brief objectives when available
8. All new code has regression tests
9. Full test suite passes (89+ existing + new Stage 3 tests)
10. North-star document updated with Stage 3 sub-stage status

## Out of scope for Stage 3

- LLM-powered brief generation (user writes the brief manually or via API)
- LLM-powered task plan generation (future Stage 4 candidate)
- Brief versioning / history (upsert is sufficient for now)
- CSS/styling beyond functional HTML structure
- Form-based UI for brief/plan editing (API-first; forms are Stage 4 candidate)

## Dependency map

```
Task 1 (3A: ProjectRecord)
  └── Task 5 (3E: Landing page needs list_projects)
  └── Task 4 (3D: Homepage needs enriched project)

Task 2 (3B: ResearchBrief)
  └── Task 4 (3D: Homepage renders brief)
  └── Task 6 (3F: Context injection reads brief)

Task 3 (3C: TaskPlan)
  └── Task 4 (3D: Homepage renders plan)

Task 7 (north-star update) — independent, can run any time
```

Parallelizable: Tasks 1-3 can be implemented concurrently. Task 4 depends on all three. Task 5 depends on Task 1. Task 6 depends on Task 2.
