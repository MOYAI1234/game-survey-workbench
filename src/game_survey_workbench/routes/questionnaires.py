from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.errors import (
    LLM_CONFIG_ERROR_MESSAGE,
    NoKnowledgeMatchedError,
    NoKnowledgeSelectedError,
    ProjectNotFoundError,
)
from game_survey_workbench.llm.client import (
    MissingLLMConfigurationError,
    build_llm_client,
)
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.models.questionnaire import (
    QuestionnaireDraftRequest,
    QuestionnaireSpecVersion,
)
from game_survey_workbench.services.download_utils import strip_markdown
from game_survey_workbench.services.questionnaires import generate_questionnaire_draft
from game_survey_workbench.services.questionnaires import refine_questionnaire_draft
from game_survey_workbench.services.questionnaire_versions import (
    diff_versions,
    list_versions,
)
from game_survey_workbench.services.projects import get_project

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _generate_questionnaire_version(
    *,
    project_slug: str,
    payload: QuestionnaireDraftRequest,
    bilingual: bool = False,
) -> QuestionnaireSpecVersion:
    settings = get_settings()
    client = build_llm_client(settings)
    return generate_questionnaire_draft(
        project_slug=project_slug,
        payload=payload,
        workspace_root=settings.workspace_root,
        client=client,
        bilingual=bilingual,
    )


@router.post("/projects/{project_slug}/questionnaires/draft", status_code=status.HTTP_201_CREATED)
def create_questionnaire_draft(project_slug: str, payload: QuestionnaireDraftRequest):
    try:
        version = _generate_questionnaire_version(project_slug=project_slug, payload=payload)
    except MissingLLMConfigurationError as exc:
        raise HTTPException(status_code=500, detail=LLM_CONFIG_ERROR_MESSAGE) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except NoKnowledgeSelectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NoKnowledgeMatchedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "version_id": version.version_id,
        "markdown_spec": version.markdown_spec,
        "citations": version.citations,
    }


@router.post("/projects/{project_slug}/questionnaires/draft-form")
def draft_questionnaire_form(
    project_slug: str,
    research_goal: str = Form(...),
    bilingual: bool = Form(False),
):
    try:
        _generate_questionnaire_version(
            project_slug=project_slug,
            payload=QuestionnaireDraftRequest(research_goal=research_goal),
            bilingual=bilingual,
        )
    except MissingLLMConfigurationError:
        return RedirectResponse(
            url=f"/projects/{project_slug}/questionnaires/latest?error=llm_missing",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except (NoKnowledgeSelectedError, NoKnowledgeMatchedError) as exc:
        return RedirectResponse(
            url=f"/projects/{project_slug}/questionnaires/latest?error={str(exc)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    return RedirectResponse(
        url=f"/projects/{project_slug}/questionnaires/latest",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/projects/{project_slug}/questionnaires/refine-form")
def refine_questionnaire_form(
    project_slug: str,
    version_id: str = Form(...),
    feedback: str = Form(...),
):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        current_version = session.exec(
            select(QuestionnaireSpecVersion).where(
                QuestionnaireSpecVersion.project_slug == project_slug,
                QuestionnaireSpecVersion.version_id == version_id,
            )
        ).first()
    if current_version is None:
        raise HTTPException(status_code=404, detail="Questionnaire version not found")

    project = get_project(workspace_root=settings.workspace_root, project_slug=project_slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        client = build_llm_client(settings)
        refined = refine_questionnaire_draft(
            llm_client=client,
            previous_markdown=current_version.markdown_spec,
            feedback=feedback,
            research_goal=current_version.research_goal,
            knowledge_snippets=current_version.retrieved_snippets,
            parent_version_id=current_version.version_id,
        )
    except MissingLLMConfigurationError:
        return RedirectResponse(
            url=f"/projects/{project_slug}/questionnaires/latest?error=llm_missing",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception:
        return RedirectResponse(
            url=f"/projects/{project_slug}/questionnaires/latest?error=refine_failed",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    save_payload = QuestionnaireDraftRequest(
        research_goal=refined.research_goal,
        hypotheses=[],
        knowledge_snippets=[],
    )
    from game_survey_workbench.services.questionnaires import save_questionnaire_draft

    save_questionnaire_draft(
        project_slug=project_slug,
        project_name=project.name,
        payload=save_payload,
        workspace_root=settings.workspace_root,
        markdown_spec=refined.markdown_spec,
        citations=current_version.citations,
        retrieved_snippets=current_version.retrieved_snippets,
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
        versions = list_versions(session, project_slug)
        knowledge_count = len(list(session.exec(select(KnowledgeDocument)).all()))

    latest = None
    if versions:
        latest = versions[0]

    return templates.TemplateResponse(
        request,
        "questionnaires/detail.html",
        {
            "project_slug": project_slug,
            "spec": latest,
            "version_count": len(versions),
            "fallback_notice": None,
            "error_message": (
                LLM_CONFIG_ERROR_MESSAGE
                if request.query_params.get("error") == "llm_missing"
                else request.query_params.get("error")
                if request.query_params.get("error")
                else None
            ),
        },
    )


@router.get("/projects/{project_slug}/questionnaires/history", response_class=HTMLResponse)
def questionnaire_history(
    project_slug: str,
    request: Request,
    from_version: str | None = None,
    to_version: str | None = None,
):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        versions = list_versions(session, project_slug)
        version_diff = None
        if from_version and to_version:
            version_diff = diff_versions(
                session,
                project_slug,
                from_version,
                to_version,
            )

    return templates.TemplateResponse(
        request,
        "questionnaires/history.html",
        {
            "project_slug": project_slug,
            "versions": versions,
            "version_diff": version_diff,
            "from_version": from_version,
            "to_version": to_version,
        },
    )


@router.get("/projects/{project_slug}/questionnaires/{version_id}/download")
def download_questionnaire(
    project_slug: str,
    version_id: str,
    fmt: str = "md",
):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        version = session.exec(
            select(QuestionnaireSpecVersion).where(
                QuestionnaireSpecVersion.project_slug == project_slug,
                QuestionnaireSpecVersion.version_id == version_id,
            )
        ).first()

    if version is None:
        raise HTTPException(status_code=404, detail="Questionnaire version not found")

    normalized_fmt = "txt" if fmt == "txt" else "md"
    if normalized_fmt == "txt":
        media_type = "text/plain; charset=utf-8"
        content = strip_markdown(version.markdown_spec)
    else:
        media_type = "text/markdown; charset=utf-8"
        content = version.markdown_spec

    filename = f"{project_slug}-questionnaire-{version_id}.{normalized_fmt}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
