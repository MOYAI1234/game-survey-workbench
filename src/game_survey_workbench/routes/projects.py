from pathlib import Path

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from game_survey_workbench.config import get_settings
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.research_brief import ResearchBriefPayload
from game_survey_workbench.models.task_plan import TaskPlanPayload
from game_survey_workbench.services.projects import create_project, get_project
from game_survey_workbench.services.research_brief import (
    get_research_brief,
    save_research_brief,
)
from game_survey_workbench.services.task_plan import get_task_plan, save_task_plan

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project_route(payload: ProjectCreate):
    settings = get_settings()
    project = create_project(payload, workspace_root=settings.workspace_root)
    return {
        "slug": project.slug,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "updated_at": project.updated_at,
        "knowledge_pack": project.knowledge_pack,
    }


@router.get("/projects/{project_slug}", response_class=HTMLResponse)
def project_detail(project_slug: str, request: Request):
    settings = get_settings()
    project = get_project(
        workspace_root=settings.workspace_root,
        project_slug=project_slug,
    )
    brief = get_research_brief(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    plan = get_task_plan(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
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


@router.put("/projects/{project_slug}/plan")
def upsert_plan(project_slug: str, payload: TaskPlanPayload):
    settings = get_settings()
    plan = save_task_plan(
        project_slug=project_slug,
        payload=payload,
        workspace_root=settings.workspace_root,
    )
    return {
        "project_slug": plan.project_slug,
        "tasks": plan.tasks,
    }


@router.get("/projects/{project_slug}/plan")
def read_plan(project_slug: str):
    settings = get_settings()
    plan = get_task_plan(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    if plan is None:
        return {"project_slug": project_slug, "plan": None}
    return {
        "project_slug": plan.project_slug,
        "tasks": plan.tasks,
    }
