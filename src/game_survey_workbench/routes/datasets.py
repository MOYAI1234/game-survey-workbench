from pathlib import Path

from tempfile import NamedTemporaryFile

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.analysis_run import AnalysisRunRecord
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.services.analysis_context import (
    build_deterministic_findings_for_run,
    load_analysis_run_context,
)
from game_survey_workbench.services.dataset_import import import_dataset, store_uploaded_dataset
from game_survey_workbench.services.reporting import (
    get_coding_results,
    get_latest_insight_record,
    list_insight_records,
)
from game_survey_workbench.services.workflow_state import get_workflow_state

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


async def _import_uploaded_dataset(*, project_slug: str, file: UploadFile):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        project = session.exec(
            select(ProjectRecord).where(ProjectRecord.slug == project_slug)
        ).first()

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    suffix = Path(file.filename or "upload.csv").suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Unsupported dataset format")

    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(await file.read())

    stored_path = store_uploaded_dataset(
        source_path=temp_path,
        filename=file.filename or f"dataset{suffix}",
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    temp_path.unlink(missing_ok=True)

    try:
        dataset = import_dataset(stored_path, project_slug=project_slug, workspace_root=settings.workspace_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return dataset


@router.post("/projects/{project_slug}/datasets/import", status_code=status.HTTP_201_CREATED)
async def import_dataset_route(project_slug: str, file: UploadFile = File(...)):
    dataset = await _import_uploaded_dataset(project_slug=project_slug, file=file)
    return dataset.model_dump()


@router.post("/projects/{project_slug}/datasets/import-form")
async def import_dataset_form(project_slug: str, file: UploadFile = File(...)):
    dataset = await _import_uploaded_dataset(project_slug=project_slug, file=file)
    return RedirectResponse(
        url=f"/projects/{project_slug}/analysis/{dataset.analysis_run_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _find_latest_analysis_run_id(*, project_slug: str, workspace_root: Path) -> str | None:
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        runs = session.exec(
            select(AnalysisRunRecord).where(AnalysisRunRecord.project_slug == project_slug)
        ).all()
    if not runs:
        return None
    return sorted(runs, key=lambda item: item.created_at, reverse=True)[0].analysis_run_id


def _render_analysis_detail(*, project_slug: str, analysis_run_id: str | None, request: Request):
    context = {
        "project_slug": project_slug,
        "run_id": analysis_run_id,
        "findings": [],
        "schema": {},
        "coding_results": [],
        "insight": None,
    }
    if analysis_run_id is None:
        return templates.TemplateResponse(request, "analysis/detail.html", context)

    settings = get_settings()
    loaded_context = load_analysis_run_context(
        analysis_run_id=analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    if loaded_context.analysis_run.project_slug != project_slug:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    context["findings"] = build_deterministic_findings_for_run(
        analysis_run_id=analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    context["schema"] = loaded_context.dataset_record.dataset_schema
    context["coding_results"] = get_coding_results(
        analysis_run_id=analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    context["insight"] = get_latest_insight_record(
        analysis_run_id=analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    context["insight_history"] = list_insight_records(
        analysis_run_id=analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    workflow = get_workflow_state(loaded_context.analysis_run.workflow_state)
    context["workflow_phase"] = workflow.current_phase
    context["workflow_error"] = workflow.last_error
    context["workflow_completed"] = workflow.completed_phases
    return templates.TemplateResponse(request, "analysis/detail.html", context)


@router.get("/projects/{project_slug}/analysis/latest", response_class=HTMLResponse)
def analysis_detail(project_slug: str, request: Request):
    settings = get_settings()
    latest_run_id = _find_latest_analysis_run_id(
        project_slug=project_slug,
        workspace_root=settings.workspace_root,
    )
    return _render_analysis_detail(
        project_slug=project_slug,
        analysis_run_id=latest_run_id,
        request=request,
    )


@router.get("/projects/{project_slug}/analysis/{analysis_run_id}", response_class=HTMLResponse)
def analysis_detail_by_id(project_slug: str, analysis_run_id: str, request: Request):
    if analysis_run_id == "latest":
        return analysis_detail(project_slug=project_slug, request=request)
    return _render_analysis_detail(
        project_slug=project_slug,
        analysis_run_id=analysis_run_id,
        request=request,
    )
