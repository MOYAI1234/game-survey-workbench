from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.services.dataset_import import import_dataset

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.post("/projects/{project_slug}/datasets/import", status_code=status.HTTP_201_CREATED)
def import_dataset_route(project_slug: str):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        project = session.exec(
            select(ProjectRecord).where(ProjectRecord.slug == project_slug)
        ).first()

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    default_csv = settings.workspace_root / "projects" / project_slug / "data" / "raw" / "dataset.csv"
    if not default_csv.exists():
        raise HTTPException(status_code=404, detail="Dataset file not found")

    dataset = import_dataset(default_csv, project_slug=project_slug, workspace_root=settings.workspace_root)
    return dataset.model_dump()


@router.get("/projects/{project_slug}/analysis/latest", response_class=HTMLResponse)
def analysis_detail(project_slug: str, request: Request):
    return templates.TemplateResponse(
        request,
        "analysis/detail.html",
        {"project_slug": project_slug},
    )
