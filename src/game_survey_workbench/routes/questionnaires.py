from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.errors import NoKnowledgeMatchedError, ProjectNotFoundError
from game_survey_workbench.llm.client import (
    MissingLLMConfigurationError,
    build_llm_client,
)
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.questionnaire import (
    QuestionnaireDraftRequest,
    QuestionnaireSpecVersion,
)
from game_survey_workbench.services.questionnaires import generate_questionnaire_draft

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _generate_questionnaire_version(
    *, project_slug: str, payload: QuestionnaireDraftRequest
) -> QuestionnaireSpecVersion:
    settings = get_settings()
    try:
        client = build_llm_client(settings)
        return generate_questionnaire_draft(
            project_slug=project_slug,
            payload=payload,
            workspace_root=settings.workspace_root,
            client=client,
        )
    except MissingLLMConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except NoKnowledgeMatchedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_slug}/questionnaires/draft", status_code=status.HTTP_201_CREATED)
def create_questionnaire_draft(project_slug: str, payload: QuestionnaireDraftRequest):
    version = _generate_questionnaire_version(project_slug=project_slug, payload=payload)
    return {
        "version_id": version.version_id,
        "markdown_spec": version.markdown_spec,
        "citations": version.citations,
    }


@router.post("/projects/{project_slug}/questionnaires/draft-form")
def draft_questionnaire_form(
    project_slug: str,
    research_goal: str = Form(...),
):
    _generate_questionnaire_version(
        project_slug=project_slug,
        payload=QuestionnaireDraftRequest(research_goal=research_goal),
    )
    return RedirectResponse(
        url=f"/projects/{project_slug}/questionnaires/latest",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/projects/{project_slug}/questionnaires/latest", response_class=HTMLResponse)
def questionnaire_detail(project_slug: str, request: Request):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        versions = session.exec(
            select(QuestionnaireSpecVersion).where(
                QuestionnaireSpecVersion.project_slug == project_slug
            )
        ).all()

    latest = None
    if versions:
        latest = sorted(versions, key=lambda item: item.created_at, reverse=True)[0]

    return templates.TemplateResponse(
        request,
        "questionnaires/detail.html",
        {
            "project_slug": project_slug,
            "spec": latest,
        },
    )
