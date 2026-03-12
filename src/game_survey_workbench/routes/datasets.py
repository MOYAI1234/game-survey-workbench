from pathlib import Path

from tempfile import NamedTemporaryFile

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.services.dataset_import import import_dataset, store_uploaded_dataset

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.post("/projects/{project_slug}/datasets/import", status_code=status.HTTP_201_CREATED)
async def import_dataset_route(project_slug: str, file: UploadFile = File(...)):
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

    dataset = import_dataset(stored_path, project_slug=project_slug, workspace_root=settings.workspace_root)
    return dataset.model_dump()


@router.get("/projects/{project_slug}/analysis/latest", response_class=HTMLResponse)
def analysis_detail(project_slug: str, request: Request):
    return templates.TemplateResponse(
        request,
        "analysis/detail.html",
        {"project_slug": project_slug},
    )
