from pathlib import Path

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from game_survey_workbench.config import get_settings
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project_route(payload: ProjectCreate):
    settings = get_settings()
    project = create_project(payload, workspace_root=settings.workspace_root)
    return {
        "slug": project.slug,
        "name": project.name,
        "knowledge_pack": project.knowledge_pack,
    }


@router.get("/projects/{project_slug}", response_class=HTMLResponse)
def project_detail(project_slug: str, request: Request):
    return templates.TemplateResponse(
        request,
        "projects/detail.html",
        {"project_slug": project_slug},
    )
