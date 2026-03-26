from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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
    build_text_coding_client,
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
from game_survey_workbench.services.coding_progress import (
    get_coding_progress_snapshot,
    mark_analysis_run_active,
    unmark_analysis_run_active,
)
from game_survey_workbench.services.text_coding import (
    code_open_text_column_with_status,
)
from game_survey_workbench.services.workflow_state import record_workflow_event

router = APIRouter()
DEFAULT_TEXT_CODING_MAX_WORKERS = 1


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


@router.post("/projects/{project_slug}/analysis/latest/code-text-all/start")
def start_code_text_all_latest(project_slug: str):
    settings = get_settings()
    latest_run_id = _find_latest_analysis_run_id(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    if latest_run_id is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return start_code_text_all(project_slug=project_slug, analysis_run_id=latest_run_id)


@router.get("/projects/{project_slug}/analysis/latest/coding-status")
def coding_status_latest(project_slug: str):
    settings = get_settings()
    latest_run_id = _find_latest_analysis_run_id(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    if latest_run_id is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return coding_status(project_slug=project_slug, analysis_run_id=latest_run_id)


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
        client = build_text_coding_client(settings)
        responses = load_free_text_responses_for_question(
            analysis_run_id=analysis_run_id,
            question_column=payload.question_column,
            workspace_root=settings.workspace_root,
        )
        result, execution_status = code_open_text_column_with_status(
            project_slug=project_slug,
            analysis_run_id=analysis_run_id,
            question_column=payload.question_column,
            responses=responses,
            workspace_root=settings.workspace_root,
            client=client,
        )
        if execution_status == "done":
            record_workflow_event(
                workspace_root=settings.workspace_root,
                analysis_run_id=analysis_run_id,
                event="coding_complete",
            )
        else:
            record_workflow_event(
                workspace_root=settings.workspace_root,
                analysis_run_id=analysis_run_id,
                event="coding_failed",
                error=(
                    f"Text coding finished with status '{execution_status}' "
                    f"for question '{payload.question_column}'."
                ),
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


def _execute_code_text_all(*, project_slug: str, analysis_run_id: str) -> None:
    settings = get_settings()
    client = build_text_coding_client(settings)
    context = load_analysis_run_context(
        analysis_run_id=analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    free_text_questions: list[tuple[str, list[str]]] = []
    for question_column, payload in context.dataset_record.dataset_schema.items():
        if not isinstance(payload, dict):
            continue
        schema = QuestionColumnSchema.model_validate(payload)
        if schema.question_type != "free_text":
            continue
        responses = load_free_text_responses_for_question(
            analysis_run_id=analysis_run_id,
            question_column=question_column,
            workspace_root=settings.workspace_root,
        )
        free_text_questions.append((question_column, responses))

    if not free_text_questions:
        return

    statuses: list[str] = []
    errors: list[str] = []
    max_workers = min(
        max(1, settings.text_coding_max_workers or DEFAULT_TEXT_CODING_MAX_WORKERS),
        len(free_text_questions),
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                code_open_text_column_with_status,
                project_slug=project_slug,
                analysis_run_id=analysis_run_id,
                question_column=question_column,
                responses=responses,
                workspace_root=settings.workspace_root,
                client=client,
            ): question_column
            for question_column, responses in free_text_questions
        }

        for future in as_completed(futures):
            question_column = futures[future]
            try:
                _result, execution_status = future.result()
                statuses.append(execution_status)
            except Exception as exc:
                errors.append(f"{question_column}: {exc}")

    if errors or any(status != "done" for status in statuses):
        detail_parts = list(errors)
        non_done = [status for status in statuses if status != "done"]
        if non_done:
            detail_parts.append(
                "Non-complete coding statuses: " + ", ".join(sorted(non_done))
            )
        record_workflow_event(
            workspace_root=settings.workspace_root,
            analysis_run_id=analysis_run_id,
            event="coding_failed",
            error="; ".join(detail_parts),
        )
    else:
        record_workflow_event(
            workspace_root=settings.workspace_root,
            analysis_run_id=analysis_run_id,
            event="coding_complete",
        )


def _run_code_text_all_background(*, project_slug: str, analysis_run_id: str) -> None:
    try:
        _execute_code_text_all(
            project_slug=project_slug,
            analysis_run_id=analysis_run_id,
        )
    except MissingLLMConfigurationError:
        settings = get_settings()
        record_workflow_event(
            workspace_root=settings.workspace_root,
            analysis_run_id=analysis_run_id,
            event="coding_failed",
            error=LLM_CONFIG_ERROR_MESSAGE,
        )
    except Exception as exc:
        settings = get_settings()
        record_workflow_event(
            workspace_root=settings.workspace_root,
            analysis_run_id=analysis_run_id,
            event="coding_failed",
            error=str(exc),
        )
    finally:
        unmark_analysis_run_active(analysis_run_id)


def start_code_text_all_background(*, project_slug: str, analysis_run_id: str, workspace_root) -> bool:
    if not mark_analysis_run_active(analysis_run_id):
        return False
    thread = threading.Thread(
        target=_run_code_text_all_background,
        kwargs={
            "project_slug": project_slug,
            "analysis_run_id": analysis_run_id,
        },
        daemon=True,
        name=f"text-coding-{analysis_run_id}",
    )
    thread.start()
    return True


@router.post("/projects/{project_slug}/analysis/{analysis_run_id}/code-text-all/start")
def start_code_text_all(project_slug: str, analysis_run_id: str):
    settings = get_settings()
    analysis_run = get_analysis_run(
        analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    if analysis_run is None or analysis_run.project_slug != project_slug:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    start_code_text_all_background(
        project_slug=project_slug,
        analysis_run_id=analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    return RedirectResponse(
        url=f"/projects/{project_slug}/analysis/latest",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/projects/{project_slug}/analysis/{analysis_run_id}/coding-status")
def coding_status(project_slug: str, analysis_run_id: str):
    settings = get_settings()
    analysis_run = get_analysis_run(
        analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    if analysis_run is None or analysis_run.project_slug != project_slug:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return get_coding_progress_snapshot(
        workspace_root=settings.workspace_root,
        analysis_run_id=analysis_run_id,
    )


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
        _execute_code_text_all(
            project_slug=project_slug,
            analysis_run_id=analysis_run_id,
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
