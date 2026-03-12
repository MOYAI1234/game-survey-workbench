from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.dataset import DatasetRecord
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.models.reporting import ReportGenerateRequest
from game_survey_workbench.services.reporting import save_report

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.post("/projects/{project_slug}/reports/generate", status_code=status.HTTP_201_CREATED)
def generate_report(project_slug: str, payload: ReportGenerateRequest):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        project = session.exec(
            select(ProjectRecord).where(ProjectRecord.slug == project_slug)
        ).first()
        dataset = session.exec(
            select(DatasetRecord).where(
                DatasetRecord.analysis_run_id == payload.analysis_run_id,
                DatasetRecord.project_slug == project_slug,
            )
        ).first()

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if dataset is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    path = save_report(
        project_slug=project_slug,
        analysis_run_id=payload.analysis_run_id,
        workspace_root=settings.workspace_root,
        title=f"{project.name} Report",
        summary_points=["Initial automated summary."],
        sections={"Key Findings": ["Analysis run completed."]},
    )
    return {"path": str(path), "analysis_run_id": payload.analysis_run_id}


@router.get("/projects/{project_slug}/reports/latest", response_class=HTMLResponse)
def report_detail(project_slug: str, request: Request):
    return templates.TemplateResponse(
        request,
        "analysis/detail.html",
        {"project_slug": project_slug},
    )
