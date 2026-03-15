from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.services.projects import list_projects

TEMPLATE_ROOT = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_ROOT))

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    settings = get_settings()
    projects = list_projects(workspace_root=settings.workspace_root)
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        knowledge_documents = list(
            session.exec(
                select(KnowledgeDocument).order_by(KnowledgeDocument.id.desc())
            ).all()
        )
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "projects": projects,
            "workflows": ["问卷设计", "数据分析", "报告生成"],
            "knowledge_count": len(knowledge_documents),
            "recent_knowledge_documents": knowledge_documents[:5],
        },
    )
