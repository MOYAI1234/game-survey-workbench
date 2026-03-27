from pathlib import Path

import mistune
from fastapi import APIRouter, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import get_engine
from game_survey_workbench.errors import LLM_CONFIG_ERROR_MESSAGE
from game_survey_workbench.llm.client import MissingLLMConfigurationError
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.models.reporting import ReportGenerateRequest, ReportRecord
from game_survey_workbench.routes.datasets import _find_latest_analysis_run_id
from game_survey_workbench.services.analysis_context import (
    build_deterministic_findings_for_run,
    load_analysis_run_context,
)
from game_survey_workbench.services.dataset_meta import extract_dataset_meta
from game_survey_workbench.services.download_utils import strip_markdown
from game_survey_workbench.services.knowledge_feedback import (
    KnowledgeFeedbackPayload,
    save_report_findings_as_knowledge,
)
from game_survey_workbench.services.research_brief import get_research_brief
from game_survey_workbench.services.research_waves import get_current_research_wave
from game_survey_workbench.services.reporting import (
    generate_structured_report,
    get_analysis_run_record,
    get_coding_results,
    get_latest_insight_record,
    parse_report_markdown,
    save_report,
)
from game_survey_workbench.services.report_versions import list_report_versions
from game_survey_workbench.services.workflow_state import record_workflow_event

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
templates.env.filters["markdown"] = mistune.create_markdown(escape=False)


def _serve_report_file(report: ReportRecord, *, fmt: str = "md") -> Response:
    path_obj = Path(report.path)
    if not path_obj.exists():
        raise HTTPException(status_code=404, detail="Report file not found on disk")

    normalized_fmt = "txt" if fmt == "txt" else "md"
    markdown = path_obj.read_text(encoding="utf-8")
    if normalized_fmt == "txt":
        media_type = "text/plain; charset=utf-8"
        content = strip_markdown(markdown)
    else:
        media_type = "text/markdown; charset=utf-8"
        content = markdown

    filename = f"{report.project_slug}-report-{report.id}.{normalized_fmt}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    analysis_context = load_analysis_run_context(
        analysis_run_id=payload.analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    brief_record = get_research_brief(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    statistical_findings = build_deterministic_findings_for_run(
        analysis_run_id=payload.analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    coded_themes = [
        theme
        for result in coding_results
        for theme in result.themes
        if isinstance(theme, dict)
    ]
    dataset_meta = extract_dataset_meta(
        schema={
            "columns": {
                column: {
                    "type": payload.get("question_type", "unknown")
                    if isinstance(payload, dict)
                    else "unknown"
                }
                for column, payload in analysis_context.dataset_record.dataset_schema.items()
            }
        },
        row_count=len(analysis_context.dataframe),
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

    language = getattr(project, "language", "zh")
    markdown = generate_structured_report(
        project_name=project.name,
        brief=brief_record.model_dump() if brief_record is not None else None,
        dataset_meta=dataset_meta,
        statistical_findings=statistical_findings,
        coded_themes=coded_themes,
        insight_narrative=narrative,
        evidence_section=evidence_section,
        language=language,
    )

    path = save_report(
        project_slug=project_slug,
        analysis_run_id=payload.analysis_run_id,
        workspace_root=settings.workspace_root,
        wave_id=analysis_run.wave_id,
        title=f"{project.name} Report",
        summary_points=summary_points,
        sections=sections,
        narrative=narrative,
        evidence=evidence,
        evidence_section=evidence_section,
        markdown=markdown,
    )
    record_workflow_event(
        workspace_root=settings.workspace_root,
        analysis_run_id=payload.analysis_run_id,
        event="report_complete",
    )
    return {"path": str(path), "analysis_run_id": payload.analysis_run_id}


@router.post("/projects/{project_slug}/reports/generate-form")
def generate_report_form(project_slug: str, analysis_run_id: str | None = Form(None)):
    settings = get_settings()
    resolved_run_id = analysis_run_id or _find_latest_analysis_run_id(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    if resolved_run_id is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    try:
        generate_report(
            project_slug=project_slug,
            payload=ReportGenerateRequest(analysis_run_id=resolved_run_id),
        )
    except MissingLLMConfigurationError:
        record_workflow_event(
            workspace_root=settings.workspace_root,
            analysis_run_id=resolved_run_id,
            event="report_failed",
            error=LLM_CONFIG_ERROR_MESSAGE,
        )
        return RedirectResponse(
            url=f"/projects/{project_slug}/analysis/latest",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        record_workflow_event(
            workspace_root=settings.workspace_root,
            analysis_run_id=resolved_run_id,
            event="report_failed",
            error=str(exc),
        )
        return RedirectResponse(
            url=f"/projects/{project_slug}/analysis/latest",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=f"/projects/{project_slug}/reports/latest",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/projects/{project_slug}/reports/latest", response_class=HTMLResponse)
def report_detail(project_slug: str, request: Request):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    current_wave = get_current_research_wave(
        workspace_root=settings.workspace_root,
        project_slug=project_slug,
    )
    with Session(engine) as session:
        statement = select(ReportRecord).where(ReportRecord.project_slug == project_slug)
        if current_wave is not None:
            statement = statement.where(ReportRecord.wave_id == current_wave.id)
        records = session.exec(statement).all()

    report_content = None
    report_display = None
    report_path = None
    if records:
        latest = sorted(records, key=lambda item: item.created_at, reverse=True)[0]
        report_path = latest.path
        path_obj = Path(report_path)
        if path_obj.exists():
            report_content = path_obj.read_text(encoding="utf-8")
            report_display = parse_report_markdown(report_content)

    return templates.TemplateResponse(
        request,
        "reports/detail.html",
        {
            "project_slug": project_slug,
            "current_wave": current_wave,
            "report_content": report_content,
            "report_display": report_display,
            "report_path": report_path,
        },
    )


@router.get("/projects/{project_slug}/reports/history", response_class=HTMLResponse)
def report_history(project_slug: str, request: Request):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    current_wave = get_current_research_wave(
        workspace_root=settings.workspace_root,
        project_slug=project_slug,
    )
    with Session(engine) as session:
        versions = list_report_versions(
            session,
            project_slug,
            wave_id=current_wave.id if current_wave is not None else None,
        )

    return templates.TemplateResponse(
        request,
        "reports/history.html",
        {
            "project_slug": project_slug,
            "current_wave": current_wave,
            "versions": versions,
        },
    )


@router.get("/projects/{project_slug}/reports/latest/download")
def download_latest_report(project_slug: str, fmt: str = "md"):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    current_wave = get_current_research_wave(
        workspace_root=settings.workspace_root,
        project_slug=project_slug,
    )
    with Session(engine) as session:
        statement = select(ReportRecord).where(ReportRecord.project_slug == project_slug)
        if current_wave is not None:
            statement = statement.where(ReportRecord.wave_id == current_wave.id)
        records = session.exec(statement).all()

    if not records:
        raise HTTPException(status_code=404, detail="No reports found")

    latest = sorted(records, key=lambda record: record.created_at, reverse=True)[0]
    return _serve_report_file(latest, fmt=fmt)


@router.get("/projects/{project_slug}/reports/{report_id}/download")
def download_report_by_id(project_slug: str, report_id: int, fmt: str = "md"):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        record = session.exec(
            select(ReportRecord).where(
                ReportRecord.id == report_id,
                ReportRecord.project_slug == project_slug,
            )
        ).first()

    if record is None:
        raise HTTPException(status_code=404, detail="Report not found")

    return _serve_report_file(record, fmt=fmt)


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
