from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.services.knowledge_ingest import (
    STAGE_LABEL_MAP,
    build_ingest_ready_markdown,
    ingest_knowledge_file,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/knowledge", response_class=HTMLResponse)
def knowledge_detail(request: Request):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    search = request.query_params.get("search", "").strip()
    stage = request.query_params.get("stage", "").strip()
    doc_type = request.query_params.get("doc_type", "").strip()
    tag = request.query_params.get("tag", "").strip()
    with Session(engine) as session:
        documents = list(
            session.exec(
                select(KnowledgeDocument).order_by(KnowledgeDocument.id.desc())
            ).all()
        )
    if search:
        lowered = search.lower()
        documents = [
            document for document in documents
            if lowered in document.title.lower()
            or lowered in document.source_path.lower()
        ]
    if stage:
        documents = [
            document for document in documents
            if stage in (document.stages or [])
        ]
    if doc_type:
        documents = [
            document for document in documents
            if document.doc_type == doc_type
        ]
    if tag:
        documents = [
            document for document in documents
            if tag in (document.tags or [])
        ]

    return templates.TemplateResponse(
        request,
        "knowledge/detail.html",
        {
            "documents": documents,
            "upload_success": request.query_params.get("upload_success"),
            "upload_error": request.query_params.get("upload_error"),
            "stage_label_map": STAGE_LABEL_MAP,
            "filters": {
                "search": search,
                "stage": stage,
                "doc_type": doc_type,
                "tag": tag,
            },
        },
    )


@router.post("/knowledge/upload")
async def upload_knowledge(
    file: UploadFile = File(...),
    purposes: list[str] = Form([]),
):
    settings = get_settings()
    knowledge_dir = settings.workspace_root / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(file.filename or "uploaded.md").name
    destination = knowledge_dir / filename
    try:
        raw = (await file.read()).decode("utf-8")
        destination.write_text(
            build_ingest_ready_markdown(
                raw=raw,
                filename=filename,
                purposes=purposes,
            ),
            encoding="utf-8",
        )
        ingest_knowledge_file(destination, project_root=settings.workspace_root)
    except Exception:
        return RedirectResponse(
            url="/knowledge?upload_error=知识文档解析失败，请检查文件内容和用途分类",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=f"/knowledge?upload_success=知识文档「{filename}」已成功上传并入库",
        status_code=status.HTTP_303_SEE_OTHER,
    )
