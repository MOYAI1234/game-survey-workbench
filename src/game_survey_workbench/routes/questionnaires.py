from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.llm.client import (
    MissingLLMConfigurationError,
    build_llm_client,
)
from game_survey_workbench.models.questionnaire import QuestionnaireDraftRequest
from game_survey_workbench.services.questionnaires import generate_questionnaire_draft

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.post("/projects/{project_slug}/questionnaires/draft", status_code=status.HTTP_201_CREATED)
def create_questionnaire_draft(project_slug: str, payload: QuestionnaireDraftRequest):
    settings = get_settings()
    try:
        client = build_llm_client(settings)
        version = generate_questionnaire_draft(
            project_slug=project_slug,
            payload=payload,
            workspace_root=settings.workspace_root,
            client=client,
        )
    except MissingLLMConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if detail == "Project not found.":
            raise HTTPException(status_code=404, detail="Project not found") from exc
        raise HTTPException(status_code=400, detail=detail) from exc

    return {
        "version_id": version.version_id,
        "markdown_spec": version.markdown_spec,
        "citations": version.citations,
    }


@router.get("/projects/{project_slug}/questionnaires/latest", response_class=HTMLResponse)
def questionnaire_detail(project_slug: str, request: Request):
    return templates.TemplateResponse(
        request,
        "questionnaires/detail.html",
        {"project_slug": project_slug},
    )
