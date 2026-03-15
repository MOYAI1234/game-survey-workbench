from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from game_survey_workbench.config import get_settings
from game_survey_workbench.errors import (
    CodingResponseFormatError,
    NoKnowledgeMatchedError,
    ProjectNotFoundError,
)
from game_survey_workbench.llm.client import (
    MissingLLMConfigurationError,
    build_llm_client,
)
from game_survey_workbench.models.analysis_run import get_analysis_run
from game_survey_workbench.models.dataset import QuestionColumnSchema
from game_survey_workbench.models.text_coding import TextCodingRequest
from game_survey_workbench.services.analysis_context import (
    NoFreeTextResponsesFoundError,
    QuestionColumnNotFoundError,
    load_analysis_run_context,
    load_free_text_responses_for_question,
)
from game_survey_workbench.services.text_coding import code_open_text_column

router = APIRouter()


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
    except MissingLLMConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (NoFreeTextResponsesFoundError, QuestionColumnNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NoKnowledgeMatchedError as exc:
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
        for question_column, payload in context.dataset_record.dataset_schema.items():
            if not isinstance(payload, dict):
                continue
            schema = QuestionColumnSchema.model_validate(payload)
            if schema.question_type != "free_text":
                continue
            try:
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
            except Exception:
                continue
    except Exception:
        pass

    return RedirectResponse(
        url=f"/projects/{project_slug}/analysis/{analysis_run_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
