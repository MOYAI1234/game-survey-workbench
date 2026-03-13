from fastapi import APIRouter, HTTPException, status

from game_survey_workbench.config import get_settings
from game_survey_workbench.llm.client import (
    MissingLLMConfigurationError,
    build_llm_client,
)
from game_survey_workbench.models.analysis_run import get_analysis_run
from game_survey_workbench.models.text_coding import TextCodingRequest
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
        result = code_open_text_column(
            project_slug=project_slug,
            analysis_run_id=analysis_run_id,
            question_column=payload.question_column,
            responses=payload.responses,
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
        "analysis_run_id": analysis_run_id,
        "question_column": result.question_column,
        "themes": result.themes,
        "uncoded_count": result.uncoded_count,
        "citations": result.citations,
    }
