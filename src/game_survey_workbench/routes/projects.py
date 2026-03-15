from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from game_survey_workbench.config import get_settings
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.research_brief import ResearchBriefPayload
from game_survey_workbench.models.task_plan import TaskPlanPayload
from game_survey_workbench.services.knowledge_ingest import (
    build_ingest_ready_markdown,
    ingest_knowledge_file,
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
    return templates.TemplateResponse(
        request,
        "projects/detail.html",
        {
            "project": project,
            "project_slug": project_slug,
            "brief": brief,
            "plan": plan,
            "upload_success": request.query_params.get("upload_success"),
            "upload_error": request.query_params.get("upload_error"),
        },
    )


@router.post("/projects/{project_slug}/knowledge/upload")
async def upload_knowledge_form(
    project_slug: str,
    file: UploadFile = File(...),
    purposes: list[str] = Form([]),
):
    settings, _project = require_project(project_slug=project_slug)
    knowledge_dir = settings.workspace_root / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(file.filename or "uploaded.md").name
    destination = knowledge_dir / filename
    try:
        raw = (await file.read()).decode("utf-8")
        destination.write_text(
            build_ingest_ready_markdown(
                raw=raw,
                filename=filename,
                purposes=purposes,
            ),
            encoding="utf-8",
        )
        ingest_knowledge_file(destination, project_root=settings.workspace_root)
    except Exception:
        return RedirectResponse(
            url=f"/projects/{project_slug}?upload_error=知识文档解析失败，请检查文件格式",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=f"/projects/{project_slug}?upload_success=知识文档「{filename}」已成功上传并入库",
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
