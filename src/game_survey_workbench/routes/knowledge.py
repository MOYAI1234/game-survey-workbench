from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/knowledge", response_class=HTMLResponse)
def knowledge_detail(request: Request):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        documents = list(
            session.exec(
                select(KnowledgeDocument).order_by(KnowledgeDocument.id.desc())
            ).all()
        )

    return templates.TemplateResponse(
        request,
        "knowledge/detail.html",
        {
            "documents": documents,
            "upload_success": request.query_params.get("upload_success"),
            "upload_error": request.query_params.get("upload_error"),
        },
    )
