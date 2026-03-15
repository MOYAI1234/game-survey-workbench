from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.models.reporting import ReportGenerateRequest
from game_survey_workbench.services.knowledge_feedback import (
    KnowledgeFeedbackPayload,
    save_report_findings_as_knowledge,
)
from game_survey_workbench.services.reporting import (
    get_analysis_run_record,
    get_coding_results,
    get_latest_insight_record,
    save_report,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.post("/projects/{project_slug}/reports/generate", status_code=status.HTTP_201_CREATED)
def generate_report(project_slug: str, payload: ReportGenerateRequest):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        project = session.exec(
            select(ProjectRecord).where(ProjectRecord.slug == project_slug)
        ).first()

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    analysis_run = get_analysis_run_record(
        analysis_run_id=payload.analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    if analysis_run is None or analysis_run.project_slug != project_slug:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    insight_record = get_latest_insight_record(
        analysis_run_id=payload.analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    coding_results = get_coding_results(
        analysis_run_id=payload.analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    summary_points = ["Initial automated summary."]
    sections = {"Key Findings": ["Analysis run completed."]}
    narrative = None
    evidence = None
    evidence_section = None
    if insight_record is not None:
        summary_points = ["Insight narrative generated from saved analysis artifacts."]
        sections = {}
        narrative = insight_record.narrative
        evidence = insight_record.citations
        evidence_section = insight_record.evidence_section
    elif coding_results:
        theme_names = [
            theme.get("theme_name", "Unnamed Theme")
            for result in coding_results
            for theme in result.themes
        ]
        if theme_names:
            summary_points = [f"Coded themes: {', '.join(theme_names)}"]

    path = save_report(
        project_slug=project_slug,
        analysis_run_id=payload.analysis_run_id,
        workspace_root=settings.workspace_root,
        title=f"{project.name} Report",
        summary_points=summary_points,
        sections=sections,
        narrative=narrative,
        evidence=evidence,
        evidence_section=evidence_section,
    )
    return {"path": str(path), "analysis_run_id": payload.analysis_run_id}


@router.get("/projects/{project_slug}/reports/latest", response_class=HTMLResponse)
def report_detail(project_slug: str, request: Request):
    return templates.TemplateResponse(
        request,
        "analysis/detail.html",
        {"project_slug": project_slug},
    )


@router.post("/reports/feedback-to-knowledge")
def feedback_to_knowledge(payload: KnowledgeFeedbackPayload):
    settings = get_settings()
    result = save_report_findings_as_knowledge(
        payload=payload,
        workspace_root=settings.workspace_root,
    )
    return {
        "file_path": str(result.file_path),
        "document_title": result.document_title,
    }
