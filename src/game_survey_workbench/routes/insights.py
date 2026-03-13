from fastapi import APIRouter, HTTPException, status

from game_survey_workbench.config import get_settings
from game_survey_workbench.errors import NoKnowledgeMatchedError, ProjectNotFoundError
from game_survey_workbench.llm.client import (
    MissingLLMConfigurationError,
    build_llm_client,
)
from game_survey_workbench.models.analysis_run import get_analysis_run
from game_survey_workbench.models.insight import InsightGenerateRequest
from game_survey_workbench.services.insights import generate_analysis_insights

router = APIRouter()


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
        result = generate_analysis_insights(
            project_slug=project_slug,
            analysis_run_id=analysis_run_id,
            research_goal=payload.research_goal,
            statistical_findings=payload.statistical_findings,
            coded_themes=payload.coded_themes,
            workspace_root=settings.workspace_root,
            client=client,
        )
    except MissingLLMConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except NoKnowledgeMatchedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "analysis_run_id": analysis_run_id,
        "narrative": result.narrative,
        "evidence_section": result.evidence_section,
        "citations": result.citations,
    }
