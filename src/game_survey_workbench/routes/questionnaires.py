from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.models.questionnaire import QuestionnaireDraftRequest
from game_survey_workbench.services.questionnaires import save_questionnaire_draft

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.post("/projects/{project_slug}/questionnaires/draft", status_code=status.HTTP_201_CREATED)
def create_questionnaire_draft(project_slug: str, payload: QuestionnaireDraftRequest):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        project = session.exec(
            select(ProjectRecord).where(ProjectRecord.slug == project_slug)
        ).first()

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    version = save_questionnaire_draft(
        project_slug=project_slug,
        project_name=project.name,
        payload=payload,
        workspace_root=settings.workspace_root,
    )
    return {"version_id": version.version_id, "markdown_spec": version.markdown_spec}


@router.get("/projects/{project_slug}/questionnaires/latest", response_class=HTMLResponse)
def questionnaire_detail(project_slug: str, request: Request):
    return templates.TemplateResponse(
        request,
        "questionnaires/detail.html",
        {"project_slug": project_slug},
    )
