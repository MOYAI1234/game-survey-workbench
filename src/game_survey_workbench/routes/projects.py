from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.models.project import ProjectCreate, ProjectRecord
from game_survey_workbench.models.research_brief import ResearchBriefPayload
from game_survey_workbench.models.task_plan import TaskPlanPayload
from game_survey_workbench.services.project_knowledge import (
    list_selected_knowledge_document_ids,
    list_selected_knowledge_documents,
    replace_project_knowledge_selection,
)
from game_survey_workbench.services.projects import create_project, get_project
from game_survey_workbench.services.research_brief import (
    get_research_brief,
    save_research_brief,
)
from game_survey_workbench.services.task_plan import get_task_plan, save_task_plan

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def require_project(*, project_slug: str):
    settings = get_settings()
    project = get_project(
        workspace_root=settings.workspace_root,
        project_slug=project_slug,
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return settings, project


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


@router.post("/projects/create")
def create_project_form(
    slug: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
):
    settings = get_settings()
    create_project(
        ProjectCreate(slug=slug, name=name, description=description),
        workspace_root=settings.workspace_root,
    )
    return RedirectResponse(url=f"/projects/{slug}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/projects/{project_slug}", response_class=HTMLResponse)
def project_detail(project_slug: str, request: Request):
    settings, project = require_project(project_slug=project_slug)
    brief = get_research_brief(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    plan = get_task_plan(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        knowledge_documents = list(
            session.exec(select(KnowledgeDocument).order_by(KnowledgeDocument.id.desc())).all()
        )
    selected_document_ids = list_selected_knowledge_document_ids(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    selected_documents = list_selected_knowledge_documents(
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
            "knowledge_count": len(knowledge_documents),
            "knowledge_documents": knowledge_documents,
            "selected_document_ids": selected_document_ids,
            "selected_documents": selected_documents,
            "upload_success": request.query_params.get("upload_success"),
            "upload_error": request.query_params.get("upload_error"),
        },
    )


@router.post("/projects/{project_slug}/knowledge-selection")
def save_project_knowledge_selection(
    project_slug: str,
    knowledge_document_ids: list[int] = Form([]),
):
    settings, _project = require_project(project_slug=project_slug)
    replace_project_knowledge_selection(
        workspace_root=settings.workspace_root,
        project_slug=project_slug,
        knowledge_document_ids=knowledge_document_ids,
    )
    return RedirectResponse(
        url=f"/projects/{project_slug}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/projects/{project_slug}/settings")
def update_project_settings(
    project_slug: str,
    language: str = Form("zh"),
):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        project = session.exec(
            select(ProjectRecord).where(ProjectRecord.slug == project_slug)
        ).first()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        project.language = language if language in {"zh", "en"} else "zh"
        session.add(project)
        session.commit()

    return RedirectResponse(
        url=f"/projects/{project_slug}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.put("/projects/{project_slug}/brief")
def upsert_brief(project_slug: str, payload: ResearchBriefPayload):
    settings, _project = require_project(project_slug=project_slug)
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
    settings, _project = require_project(project_slug=project_slug)
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


@router.post("/projects/{project_slug}/brief/save")
def save_brief_form(
    project_slug: str,
    background: str = Form(""),
    objectives: str = Form(""),
    hypotheses: str = Form(""),
    target_audience: str = Form(""),
    success_criteria: str = Form(""),
):
    settings, _project = require_project(project_slug=project_slug)
    payload = ResearchBriefPayload(
        background=background,
        objectives=[line.strip() for line in objectives.splitlines() if line.strip()],
        hypotheses=[line.strip() for line in hypotheses.splitlines() if line.strip()],
        target_audience=target_audience,
        success_criteria=success_criteria,
    )
    save_research_brief(
        project_slug=project_slug,
        payload=payload,
        workspace_root=settings.workspace_root,
    )
    return RedirectResponse(url=f"/projects/{project_slug}", status_code=status.HTTP_303_SEE_OTHER)


@router.put("/projects/{project_slug}/plan")
def upsert_plan(project_slug: str, payload: TaskPlanPayload):
    settings, _project = require_project(project_slug=project_slug)
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
    settings, _project = require_project(project_slug=project_slug)
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
