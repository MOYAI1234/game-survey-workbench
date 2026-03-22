from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

import frontmatter
from fastapi import APIRouter, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.services.knowledge_convert import (
    SUPPORTED_CONVERSION_EXTENSIONS,
    assess_conversion_quality,
    convert_to_markdown,
)
from game_survey_workbench.services.knowledge_ingest import (
    PURPOSE_STAGE_MAP,
    STAGE_LABEL_MAP,
    build_ingest_ready_markdown,
    delete_knowledge_document,
    ingest_knowledge_file,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _load_filtered_documents(
    *,
    request: Request,
) -> tuple[list[KnowledgeDocument], dict[str, str]]:
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
        stale_documents = [
            document
            for document in documents
            if not Path(document.source_path).exists()
        ]
        if stale_documents:
            for document in stale_documents:
                session.delete(document)
            session.commit()
            stale_ids = {document.id for document in stale_documents}
            documents = [
                document for document in documents if document.id not in stale_ids
            ]

    if search:
        lowered = search.lower()
        documents = [
            document
            for document in documents
            if lowered in document.title.lower()
            or lowered in document.source_path.lower()
        ]
    if stage:
        documents = [
            document for document in documents if stage in (document.stages or [])
        ]
    if doc_type:
        documents = [document for document in documents if document.doc_type == doc_type]
    if tag:
        documents = [document for document in documents if tag in (document.tags or [])]

    return documents, {
        "search": search,
        "stage": stage,
        "doc_type": doc_type,
        "tag": tag,
    }


def _render_knowledge_detail(
    request: Request,
    *,
    upload_success: str | None = None,
    upload_error: str | None = None,
) -> HTMLResponse:
    documents, filters = _load_filtered_documents(request=request)
    has_indexing_documents = any(
        document.index_status == "indexing" for document in documents
    )
    return templates.TemplateResponse(
        request,
        "knowledge/detail.html",
        {
            "documents": documents,
            "upload_success": upload_success
            if upload_success is not None
            else request.query_params.get("upload_success"),
            "upload_error": upload_error
            if upload_error is not None
            else request.query_params.get("upload_error"),
            "stage_label_map": STAGE_LABEL_MAP,
            "filters": filters,
            "has_indexing_documents": has_indexing_documents,
        },
    )


@router.get("/knowledge", response_class=HTMLResponse)
def knowledge_detail(request: Request):
    return _render_knowledge_detail(request)


@router.post("/knowledge/{document_id}/delete")
def remove_knowledge_document(document_id: int):
    settings = get_settings()
    delete_knowledge_document(document_id, project_root=settings.workspace_root)
    return RedirectResponse(
        url="/knowledge?upload_success=知识文档已从共享知识库移除",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/knowledge/upload")
async def upload_knowledge(
    request: Request,
    file: UploadFile = File(...),
    purposes: list[str] = Form([]),
):
    settings = get_settings()
    knowledge_dir = settings.workspace_root / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(file.filename or "uploaded.md").name
    suffix = Path(filename).suffix.lower()

    if suffix in SUPPORTED_CONVERSION_EXTENSIONS:
        return await _handle_conversion_upload(
            request=request,
            file=file,
            filename=filename,
            suffix=suffix,
            workspace_root=settings.workspace_root,
        )

    if suffix not in {".md", ".txt"}:
        supported = ", ".join([".md", ".txt", *sorted(SUPPORTED_CONVERSION_EXTENSIONS)])
        return RedirectResponse(
            url=f"/knowledge?upload_error=不支持的文件格式：{suffix}。支持的格式：{supported}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

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


@router.post("/knowledge/convert-preview", response_class=HTMLResponse)
async def convert_preview(request: Request, file: UploadFile = File(...)):
    settings = get_settings()
    filename = Path(file.filename or "uploaded.bin").name
    suffix = Path(filename).suffix.lower()
    return await _handle_conversion_upload(
        request=request,
        file=file,
        filename=filename,
        suffix=suffix,
        workspace_root=settings.workspace_root,
    )


async def _handle_conversion_upload(
    *,
    request: Request,
    file: UploadFile,
    filename: str,
    suffix: str,
    workspace_root: Path,
) -> HTMLResponse:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
        tmp_path = Path(temporary_file.name)
        temporary_file.write(await file.read())

    conversion = convert_to_markdown(tmp_path)
    tmp_path.unlink(missing_ok=True)

    if not conversion.success:
        return _render_knowledge_detail(
            request,
            upload_error=conversion.error_message or "转换失败，该格式暂不支持，请手动转为 .md 后上传",
        )

    markdown_text = conversion.markdown_text or ""
    quality = assess_conversion_quality(markdown_text)

    inferred_title = Path(filename).stem
    for line in markdown_text.splitlines():
        candidate = line.lstrip("# ").strip()
        if candidate:
            inferred_title = candidate
            break

    staging_dir = workspace_root / "knowledge" / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_id = uuid4().hex[:12]
    staging_path = staging_dir / f"{staging_id}.md"
    staging_path.write_text(markdown_text, encoding="utf-8")

    return templates.TemplateResponse(
        request,
        "knowledge/convert_preview.html",
        {
            "staging_id": staging_id,
            "original_filename": filename,
            "source_format": conversion.source_format,
            "markdown_text": markdown_text,
            "quality": quality,
            "inferred_title": inferred_title,
        },
    )


@router.post("/knowledge/convert-confirm")
async def convert_confirm(request: Request):
    settings = get_settings()
    form = await request.form()
    staging_id = str(form.get("staging_id", "")).strip()
    source_format = str(form.get("source_format", "")).strip()
    title = str(form.get("title", "")).strip() or "Untitled"
    doc_type = str(form.get("doc_type", "guide")).strip() or "guide"
    purposes = form.getlist("purposes")

    staging_dir = settings.workspace_root / "knowledge" / "staging"
    staging_path = staging_dir / f"{staging_id}.md"

    if not staging_path.exists():
        return RedirectResponse(
            url="/knowledge?upload_error=转换暂存文件已过期，请重新上传",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        raw_markdown = staging_path.read_text(encoding="utf-8")
        mapped_stages = [
            PURPOSE_STAGE_MAP[purpose] for purpose in purposes if purpose in PURPOSE_STAGE_MAP
        ]
        post = frontmatter.Post(
            raw_markdown,
            title=title,
            doc_type=doc_type,
            stage=mapped_stages,
            tags=[],
            priority=0,
        )
        final_markdown = frontmatter.dumps(post)

        knowledge_dir = settings.workspace_root / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = f"{title.replace(' ', '_').replace('/', '_')}.md"
        destination = knowledge_dir / safe_filename
        if destination.exists():
            destination = knowledge_dir / f"{staging_id}_{safe_filename}"
        destination.write_text(final_markdown, encoding="utf-8")

        result = ingest_knowledge_file(destination, project_root=settings.workspace_root)

        engine = get_engine(settings.workspace_root)
        with Session(engine) as session:
            document = session.exec(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.title == result.document_title)
                .order_by(KnowledgeDocument.id.desc())
            ).first()
            if document is not None:
                document.source_format = source_format
                session.add(document)
                session.commit()

    except Exception as exc:
        return RedirectResponse(
            url=f"/knowledge?upload_error=入库失败：{exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    finally:
        staging_path.unlink(missing_ok=True)

    return RedirectResponse(
        url=f"/knowledge?upload_success=知识文档「{title}」（从 {source_format.upper()} 转换）已成功入库",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/knowledge/convert-download")
async def convert_download(request: Request):
    settings = get_settings()
    form = await request.form()
    staging_id = str(form.get("staging_id", "")).strip()

    staging_dir = settings.workspace_root / "knowledge" / "staging"
    staging_path = staging_dir / f"{staging_id}.md"

    if not staging_path.exists():
        return RedirectResponse(
            url="/knowledge?upload_error=转换暂存文件已过期，请重新上传",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return FileResponse(
        path=staging_path,
        media_type="text/markdown",
        filename=f"converted_{staging_id}.md",
    )
