from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from game_survey_workbench.config import get_settings
from game_survey_workbench.errors import (
    CodingResponseFormatError,
    LLM_CONFIG_ERROR_MESSAGE,
    ProjectNotFoundError,
)
from game_survey_workbench.llm.client import (
    MissingLLMConfigurationError,
    build_llm_client,
)
from game_survey_workbench.models.analysis_run import get_analysis_run
from game_survey_workbench.models.dataset import QuestionColumnSchema
from game_survey_workbench.models.text_coding import TextCodingRequest
from game_survey_workbench.routes.datasets import _find_latest_analysis_run_id
from game_survey_workbench.services.analysis_context import (
    NoFreeTextResponsesFoundError,
    QuestionColumnNotFoundError,
    load_analysis_run_context,
    load_free_text_responses_for_question,
)
from game_survey_workbench.services.text_coding import code_open_text_column
from game_survey_workbench.services.workflow_state import record_workflow_event

router = APIRouter()


@router.post("/projects/{project_slug}/analysis/latest/code-text-all")
def code_text_all_latest(project_slug: str):
    settings = get_settings()
    latest_run_id = _find_latest_analysis_run_id(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    if latest_run_id is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return code_text_all(project_slug=project_slug, analysis_run_id=latest_run_id)


@router.post(
    "/projects/{project_slug}/analysis/{analysis_run_id}/code-text",
    status_code=status.HTTP_201_CREATED,
)
def code_text_route(
    project_slug: str,
    analysis_run_id: str,
    payload: TextCodingRequest,
):
    settings = get_settings()
    analysis_run = get_analysis_run(
        analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    if analysis_run is None or analysis_run.project_slug != project_slug:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    try:
        client = build_llm_client(settings)
        responses = load_free_text_responses_for_question(
            analysis_run_id=analysis_run_id,
            question_column=payload.question_column,
            workspace_root=settings.workspace_root,
        )
        result = code_open_text_column(
            project_slug=project_slug,
            analysis_run_id=analysis_run_id,
            question_column=payload.question_column,
            responses=responses,
            workspace_root=settings.workspace_root,
            client=client,
        )
        record_workflow_event(
            workspace_root=settings.workspace_root,
            analysis_run_id=analysis_run_id,
            event="coding_complete",
        )
    except MissingLLMConfigurationError as exc:
        raise HTTPException(status_code=500, detail=LLM_CONFIG_ERROR_MESSAGE) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (NoFreeTextResponsesFoundError, QuestionColumnNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CodingResponseFormatError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "analysis_run_id": analysis_run_id,
        "question_column": result.question_column,
        "themes": result.themes,
        "uncoded_count": result.uncoded_count,
        "citations": result.citations,
    }


@router.post("/projects/{project_slug}/analysis/{analysis_run_id}/code-text-all")
def code_text_all(project_slug: str, analysis_run_id: str):
    settings = get_settings()
    analysis_run = get_analysis_run(
        analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    if analysis_run is None or analysis_run.project_slug != project_slug:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    try:
        client = build_llm_client(settings)
        context = load_analysis_run_context(
            analysis_run_id=analysis_run_id,
            workspace_root=settings.workspace_root,
        )
        had_free_text = False
        for question_column, payload in context.dataset_record.dataset_schema.items():
            if not isinstance(payload, dict):
                continue
            schema = QuestionColumnSchema.model_validate(payload)
            if schema.question_type != "free_text":
                continue
            had_free_text = True
            responses = load_free_text_responses_for_question(
                analysis_run_id=analysis_run_id,
                question_column=question_column,
                workspace_root=settings.workspace_root,
            )
            code_open_text_column(
                project_slug=project_slug,
                analysis_run_id=analysis_run_id,
                question_column=question_column,
                responses=responses,
                workspace_root=settings.workspace_root,
                client=client,
            )
        if had_free_text:
            record_workflow_event(
                workspace_root=settings.workspace_root,
                analysis_run_id=analysis_run_id,
                event="coding_complete",
            )
    except MissingLLMConfigurationError:
        record_workflow_event(
            workspace_root=settings.workspace_root,
            analysis_run_id=analysis_run_id,
            event="coding_failed",
            error=LLM_CONFIG_ERROR_MESSAGE,
        )
    except Exception as exc:
        record_workflow_event(
            workspace_root=settings.workspace_root,
            analysis_run_id=analysis_run_id,
            event="coding_failed",
            error=str(exc),
        )

    return RedirectResponse(
        url=f"/projects/{project_slug}/analysis/latest",
        status_code=status.HTTP_303_SEE_OTHER,
    )
