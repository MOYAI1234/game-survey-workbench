from pathlib import Path

from fastapi.testclient import TestClient

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.task_plan import TaskItem, TaskPlanPayload
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.task_plan import get_task_plan, save_task_plan


def _setup_project(tmp_path: Path) -> str:
    create_project(
        ProjectCreate(slug="bp-study", name="BP Study"),
        workspace_root=tmp_path,
    )
    return "bp-study"


def test_save_and_load_plan(tmp_path: Path):
    slug = _setup_project(tmp_path)
    payload = TaskPlanPayload(
        tasks=[
            TaskItem(label="Ingest knowledge docs", status="done"),
            TaskItem(label="Design questionnaire", status="pending"),
            TaskItem(label="Collect responses", status="pending"),
            TaskItem(label="Run analysis", status="pending"),
            TaskItem(label="Generate report", status="pending"),
        ]
    )

    plan = save_task_plan(project_slug=slug, payload=payload, workspace_root=tmp_path)

    assert plan.project_slug == slug
    assert len(plan.tasks) == 5
    assert plan.tasks[0]["status"] == "done"

    loaded = get_task_plan(project_slug=slug, workspace_root=tmp_path)
    assert loaded is not None
    assert len(loaded.tasks) == 5


def test_save_plan_overwrites(tmp_path: Path):
    slug = _setup_project(tmp_path)
    v1 = TaskPlanPayload(tasks=[TaskItem(label="Step A")])
    save_task_plan(project_slug=slug, payload=v1, workspace_root=tmp_path)

    v2 = TaskPlanPayload(
        tasks=[
            TaskItem(label="Step A", status="done"),
            TaskItem(label="Step B"),
        ]
    )
    save_task_plan(project_slug=slug, payload=v2, workspace_root=tmp_path)

    loaded = get_task_plan(project_slug=slug, workspace_root=tmp_path)
    assert loaded is not None
    assert len(loaded.tasks) == 2


def test_get_plan_returns_none_when_missing(tmp_path: Path):
    slug = _setup_project(tmp_path)

    assert get_task_plan(project_slug=slug, workspace_root=tmp_path) is None


def test_put_plan_route_persists_payload(client: TestClient):
    client.post("/projects", json={"slug": "bp-study", "name": "BP Study"})

    response = client.put(
        "/projects/bp-study/plan",
        json={
            "tasks": [
                {"label": "Ingest knowledge docs", "status": "done"},
                {"label": "Design questionnaire", "status": "pending"},
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_slug"] == "bp-study"
    assert len(payload["tasks"]) == 2
    assert payload["tasks"][0]["status"] == "done"


def test_get_plan_route_returns_saved_payload(client: TestClient):
    client.post("/projects", json={"slug": "bp-study", "name": "BP Study"})
    client.put(
        "/projects/bp-study/plan",
        json={
            "tasks": [
                {"label": "Step A", "status": "done"},
                {"label": "Step B", "status": "pending"},
            ]
        },
    )

    response = client.get("/projects/bp-study/plan")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_slug"] == "bp-study"
    assert payload["tasks"] == [
        {"label": "Step A", "status": "done"},
        {"label": "Step B", "status": "pending"},
    ]
