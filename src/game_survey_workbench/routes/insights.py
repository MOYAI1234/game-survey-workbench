from fastapi import APIRouter, Form, HTTPException, status
from fastapi.responses import RedirectResponse

from game_survey_workbench.config import get_settings
from game_survey_workbench.errors import (
    LLM_CONFIG_ERROR_MESSAGE,
    NoKnowledgeMatchedError,
    NoSavedCodingResultsError,
    ProjectNotFoundError,
)
from game_survey_workbench.llm.client import (
    MissingLLMConfigurationError,
    build_llm_client,
)
from game_survey_workbench.models.analysis_run import get_analysis_run
from game_survey_workbench.models.dataset import QuestionColumnSchema
from game_survey_workbench.models.insight import InsightGenerateRequest
from game_survey_workbench.routes.datasets import _find_latest_analysis_run_id
from game_survey_workbench.services.analysis_context import (
    build_crosstab_findings_for_run,
    build_deterministic_findings_for_run,
    load_analysis_run_context,
    load_saved_coding_themes,
)
from game_survey_workbench.services.insights import generate_analysis_insights
from game_survey_workbench.services.workflow_state import record_workflow_event

router = APIRouter()


def _partition_findings(findings: list[str]) -> tuple[list[str], list[str], list[str]]:
    statistical_findings: list[str] = []
    matrix_findings: list[str] = []
    ranking_findings: list[str] = []
    for finding in findings:
        if finding.startswith("Matrix battery "):
            matrix_findings.append(finding)
        elif finding.startswith("Ranking '"):
            ranking_findings.append(finding)
        else:
            statistical_findings.append(finding)
    return statistical_findings, matrix_findings, ranking_findings


def _infer_segment_columns(analysis_run_id: str) -> list[str]:
    settings = get_settings()
    context = load_analysis_run_context(
        analysis_run_id=analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    question_columns = set(context.dataset_record.dataset_schema.keys())
    other_text_columns = {
        QuestionColumnSchema.model_validate(payload).other_text_column
        for payload in context.dataset_record.dataset_schema.values()
        if isinstance(payload, dict)
    }
    return [
        column
        for column in context.dataframe.columns
        if column not in question_columns and column not in other_text_columns
    ]


@router.post(
    "/projects/{project_slug}/analysis/{analysis_run_id}/insights",
    status_code=status.HTTP_201_CREATED,
)
def generate_insights_route(
    project_slug: str,
    analysis_run_id: str,
    payload: InsightGenerateRequest,
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
        deterministic_findings = build_deterministic_findings_for_run(
            analysis_run_id=analysis_run_id,
            workspace_root=settings.workspace_root,
        )
        statistical_findings, matrix_findings, ranking_findings = _partition_findings(
            deterministic_findings
        )
        crosstab_findings: list[str] = []
        for segment_column in _infer_segment_columns(analysis_run_id):
            crosstab_findings.extend(
                build_crosstab_findings_for_run(
                    analysis_run_id=analysis_run_id,
                    workspace_root=settings.workspace_root,
                    segment_column=segment_column,
                )
            )
        coded_themes = load_saved_coding_themes(
            analysis_run_id=analysis_run_id,
            workspace_root=settings.workspace_root,
        )
        result = generate_analysis_insights(
            project_slug=project_slug,
            analysis_run_id=analysis_run_id,
            research_goal=payload.research_goal,
            statistical_findings=statistical_findings,
            coded_themes=coded_themes,
            workspace_root=settings.workspace_root,
            client=client,
            crosstab_findings=crosstab_findings,
            matrix_findings=matrix_findings,
            ranking_findings=ranking_findings,
        )
        record_workflow_event(
            workspace_root=settings.workspace_root,
            analysis_run_id=analysis_run_id,
            event="insights_complete",
        )
    except MissingLLMConfigurationError as exc:
        raise HTTPException(status_code=500, detail=LLM_CONFIG_ERROR_MESSAGE) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except NoKnowledgeMatchedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NoSavedCodingResultsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "analysis_run_id": analysis_run_id,
        "narrative": result.narrative,
        "evidence_section": result.evidence_section,
        "citations": result.citations,
    }


@router.post("/projects/{project_slug}/analysis/{analysis_run_id}/insights-generate")
def generate_insights_form(
    project_slug: str,
    analysis_run_id: str,
    research_goal: str = Form(...),
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
        deterministic_findings = build_deterministic_findings_for_run(
            analysis_run_id=analysis_run_id,
            workspace_root=settings.workspace_root,
        )
        statistical_findings, matrix_findings, ranking_findings = _partition_findings(
            deterministic_findings
        )
        crosstab_findings: list[str] = []
        for segment_column in _infer_segment_columns(analysis_run_id):
            crosstab_findings.extend(
                build_crosstab_findings_for_run(
                    analysis_run_id=analysis_run_id,
                    workspace_root=settings.workspace_root,
                    segment_column=segment_column,
                )
            )
        coded_themes = load_saved_coding_themes(
            analysis_run_id=analysis_run_id,
            workspace_root=settings.workspace_root,
        )
        generate_analysis_insights(
            project_slug=project_slug,
            analysis_run_id=analysis_run_id,
            research_goal=research_goal,
            statistical_findings=statistical_findings,
            coded_themes=coded_themes,
            workspace_root=settings.workspace_root,
            client=client,
            crosstab_findings=crosstab_findings,
            matrix_findings=matrix_findings,
            ranking_findings=ranking_findings,
        )
        record_workflow_event(
            workspace_root=settings.workspace_root,
            analysis_run_id=analysis_run_id,
            event="insights_complete",
        )
    except MissingLLMConfigurationError:
        record_workflow_event(
            workspace_root=settings.workspace_root,
            analysis_run_id=analysis_run_id,
            event="insights_failed",
            error=LLM_CONFIG_ERROR_MESSAGE,
        )
    except Exception as exc:
        record_workflow_event(
            workspace_root=settings.workspace_root,
            analysis_run_id=analysis_run_id,
            event="insights_failed",
            error=str(exc),
        )

    return RedirectResponse(
        url=f"/projects/{project_slug}/analysis/latest",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/projects/{project_slug}/analysis/latest/insights-generate")
def generate_insights_form_latest(
    project_slug: str,
    research_goal: str = Form(...),
):
    settings = get_settings()
    latest_run_id = _find_latest_analysis_run_id(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    if latest_run_id is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return generate_insights_form(
        project_slug=project_slug,
        analysis_run_id=latest_run_id,
        research_goal=research_goal,
    )
