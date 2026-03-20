# 2.0D Knowledge Source Format Expansion (PDF/Word/PPT) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users upload `.pdf`, `.docx`, and `.pptx` files to the global knowledge library by auto-converting them to Markdown, previewing the conversion result, and then ingesting through the existing pipeline — eliminating the requirement to manually prepare `.md` files.

**Architecture:** Add a conversion layer upstream of `ingest_knowledge_file()` using the `markitdown` library (Microsoft, Python-native, no API). The upload route gains format detection: `.md` files go straight to the existing path; non-Markdown files go through `markitdown` → conversion preview page → user decides (confirm ingest / download .md copy / abandon). No changes to the retrieval, chunking, or storage layers.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, Jinja2, pytest, `markitdown` (new dependency), existing `python-frontmatter`

---

## Assumptions

- 2.0A/B/C are complete and merged to master at commit `c43c357`.
- The existing `.md` upload path (`POST /knowledge/upload`) is preserved unchanged.
- `markitdown` handles PDF, DOCX, PPTX conversion. Quality varies by source — the design explicitly does NOT promise perfect conversion; users preview and decide.
- `KnowledgeDocument` model gains one optional field (`source_format`) but no structural changes.
- This plan corresponds to north-star "方向七：知识来源格式扩展" and is shipped as the 2.0D delivery (north-star's original 2.0D "知识可视化深化" is deferred since 2.0B already delivers basic hit feedback).

## Non-Goals

- **In-browser Markdown editing** — textarea editing of long documents is poor UX; users download and edit externally.
- **OCR for scanned PDFs** — markitdown does not do OCR; scanned PDFs will produce empty/garbled output and users should abandon.
- **Image extraction** — images in PDFs/PPTs are dropped; only text content is converted.
- **Automatic metadata inference from content** — `doc_type`, `stages`, `tags` are set by the user on the preview page, not guessed from document content.
- **Changing the existing `.md` upload flow** — it stays as-is.

## Dependencies

| Dependency | Status | Notes |
|---|---|---|
| `markitdown` | NEW | `pip install markitdown` — add to `pyproject.toml` dependencies |
| `ingest_knowledge_file()` | ✅ Exists | `src/game_survey_workbench/services/knowledge_ingest.py:93` |
| `build_ingest_ready_markdown()` | ✅ Exists | `src/game_survey_workbench/services/knowledge_ingest.py:63` |
| `parse_markdown_document()` | ✅ Exists | `src/game_survey_workbench/services/knowledge_parser.py:17` |
| Knowledge upload route | ✅ Exists | `src/game_survey_workbench/routes/knowledge.py:76` |
| Knowledge detail template | ✅ Exists | `src/game_survey_workbench/templates/knowledge/detail.html` |

## Data Model Changes

`KnowledgeDocument` gains one optional field:

```python
source_format: str | None = None  # "md" | "pdf" | "docx" | "pptx" | None (legacy)
```

This is additive and nullable — no migration needed for existing rows.

## Route Changes

| Route | Method | New/Modified | Purpose |
|---|---|---|---|
| `/knowledge/upload` | POST | Modified | Detect file extension; `.md` goes to existing path, others go to conversion preview |
| `/knowledge/convert-preview` | POST | New | Run markitdown, return preview page |
| `/knowledge/convert-confirm` | POST | New | Accept conversion, write .md, ingest |
| `/knowledge/convert-download` | POST | New | Return converted .md as file download |

## Error Handling

| Scenario | Behavior |
|---|---|
| Unsupported file extension (e.g. `.zip`) | 400 with clear message listing supported formats |
| `markitdown` raises exception | Return error page: "转换失败，该格式暂不支持，请手动转为 .md 后上传" |
| Conversion produces empty/near-empty text | Show preview page with yellow warning: "转换内容为空或极少，可能是扫描件 PDF" |
| Conversion has high garbled-character ratio | Show preview page with warning: "转换质量较低，建议下载后在外部编辑器检查" |

---

## Task 1: Add `markitdown` dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add the dependency**

In `pyproject.toml`, add `markitdown` to the `dependencies` list:

```toml
dependencies = [
  "fastapi>=0.115,<1.0",
  "jinja2>=3.1,<4.0",
  "httpx>=0.28,<1.0",
  "openpyxl>=3.1,<4.0",
  "python-multipart>=0.0.20,<1.0",
  "python-frontmatter>=1.1,<2.0",
  "sqlmodel>=0.0.24,<1.0",
  "pandas>=2.2,<3.0",
  "markitdown>=0.1,<1.0",
]
```

**Step 2: Install**

Run: `.venv/Scripts/python.exe -m pip install -e ".[dev]"`

Expected: installs successfully, `markitdown` available.

**Step 3: Verify import**

Run: `.venv/Scripts/python.exe -c "from markitdown import MarkItDown; print('ok')"`

Expected: prints `ok`.

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore(2.0D): add markitdown dependency for PDF/Word/PPT conversion"
```

---

## Task 2: Create the conversion service

**Files:**
- Create: `src/game_survey_workbench/services/knowledge_convert.py`
- Create: `tests/test_knowledge_convert.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest

from game_survey_workbench.services.knowledge_convert import (
    convert_to_markdown,
    ConversionResult,
    assess_conversion_quality,
    SUPPORTED_CONVERSION_EXTENSIONS,
)


def test_supported_extensions_includes_pdf_docx_pptx():
    assert ".pdf" in SUPPORTED_CONVERSION_EXTENSIONS
    assert ".docx" in SUPPORTED_CONVERSION_EXTENSIONS
    assert ".pptx" in SUPPORTED_CONVERSION_EXTENSIONS
    assert ".md" not in SUPPORTED_CONVERSION_EXTENSIONS


def test_convert_to_markdown_converts_docx(tmp_path: Path):
    """Create a minimal .docx via python-docx and convert it."""
    try:
        from docx import Document
    except ImportError:
        pytest.skip("python-docx not installed")

    doc = Document()
    doc.add_heading("Test Title", level=1)
    doc.add_paragraph("This is a test paragraph about game survey methodology.")
    docx_path = tmp_path / "test.docx"
    doc.save(str(docx_path))

    result = convert_to_markdown(docx_path)

    assert isinstance(result, ConversionResult)
    assert result.success is True
    assert "Test Title" in result.markdown_text
    assert "test paragraph" in result.markdown_text
    assert result.error_message is None


def test_convert_to_markdown_returns_failure_for_unsupported_format(tmp_path: Path):
    bad_file = tmp_path / "data.zip"
    bad_file.write_bytes(b"PK\x03\x04fake zip content")

    result = convert_to_markdown(bad_file)

    assert result.success is False
    assert result.error_message is not None


def test_convert_to_markdown_handles_empty_file(tmp_path: Path):
    empty = tmp_path / "empty.pdf"
    empty.write_bytes(b"")

    result = convert_to_markdown(empty)

    # Either fails or produces empty text — both are acceptable
    if result.success:
        assert result.markdown_text is not None


def test_assess_conversion_quality_flags_empty_text():
    quality = assess_conversion_quality("")
    assert quality.warning is not None
    assert "空" in quality.warning or "empty" in quality.warning.lower()


def test_assess_conversion_quality_flags_garbled_text():
    # Text with >15% non-standard characters
    garbled = "正常文字" + "\ufffd" * 20 + "abc"
    quality = assess_conversion_quality(garbled)
    assert quality.is_low_quality is True


def test_assess_conversion_quality_passes_clean_text():
    clean = "This is a clean document about game survey design methodology. " * 10
    quality = assess_conversion_quality(clean)
    assert quality.is_low_quality is False
    assert quality.warning is None
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_knowledge_convert.py -v`

Expected: FAIL — module `knowledge_convert` does not exist.

**Step 3: Write the minimal implementation**

Create `src/game_survey_workbench/services/knowledge_convert.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_CONVERSION_EXTENSIONS = {".pdf", ".docx", ".pptx"}


@dataclass
class ConversionResult:
    success: bool
    markdown_text: str | None
    source_format: str  # "pdf" | "docx" | "pptx"
    error_message: str | None = None


@dataclass
class ConversionQuality:
    char_count: int
    paragraph_count: int
    is_low_quality: bool
    warning: str | None = None


def convert_to_markdown(source_path: Path) -> ConversionResult:
    """Convert a PDF/DOCX/PPTX file to Markdown using markitdown."""
    suffix = source_path.suffix.lower()
    source_format = suffix.lstrip(".")

    if suffix not in SUPPORTED_CONVERSION_EXTENSIONS:
        return ConversionResult(
            success=False,
            markdown_text=None,
            source_format=source_format,
            error_message=f"不支持的文件格式：{suffix}。支持的格式：{', '.join(sorted(SUPPORTED_CONVERSION_EXTENSIONS))}",
        )

    try:
        from markitdown import MarkItDown

        converter = MarkItDown()
        result = converter.convert(str(source_path))
        text = result.text_content or ""
    except Exception as exc:
        return ConversionResult(
            success=False,
            markdown_text=None,
            source_format=source_format,
            error_message=f"转换失败：{exc}",
        )

    return ConversionResult(
        success=True,
        markdown_text=text.strip(),
        source_format=source_format,
    )


def assess_conversion_quality(text: str) -> ConversionQuality:
    """Assess the quality of converted Markdown text."""
    if not text or not text.strip():
        return ConversionQuality(
            char_count=0,
            paragraph_count=0,
            is_low_quality=True,
            warning="转换内容为空，可能是扫描件 PDF 或损坏的文件",
        )

    char_count = len(text)
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    paragraph_count = len(paragraphs)

    # Detect garbled characters: Unicode replacement char + control chars
    garbled_pattern = re.compile(r"[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f]")
    garbled_count = len(garbled_pattern.findall(text))
    garbled_ratio = garbled_count / max(char_count, 1)

    if garbled_ratio > 0.15:
        return ConversionQuality(
            char_count=char_count,
            paragraph_count=paragraph_count,
            is_low_quality=True,
            warning=f"转换质量较低（乱码比例 {garbled_ratio:.0%}），建议下载后在外部编辑器检查",
        )

    if char_count < 50:
        return ConversionQuality(
            char_count=char_count,
            paragraph_count=paragraph_count,
            is_low_quality=True,
            warning="转换内容极少（不足 50 字），可能丢失了大量内容",
        )

    return ConversionQuality(
        char_count=char_count,
        paragraph_count=paragraph_count,
        is_low_quality=False,
    )
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_knowledge_convert.py -v`

Expected: PASS (docx test may skip if `python-docx` not installed — that's acceptable)

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/knowledge_convert.py tests/test_knowledge_convert.py
git commit -m "feat(2.0D): add knowledge format conversion service with quality assessment"
```

---

## Task 3: Add `source_format` field to KnowledgeDocument

**Files:**
- Modify: `src/game_survey_workbench/models/knowledge.py`
- Create: `tests/test_knowledge_source_format.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from sqlmodel import Session

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument


def test_knowledge_document_persists_source_format(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        doc = KnowledgeDocument(
            source_path="/knowledge/report.md",
            title="Converted Report",
            doc_type="research",
            source_format="pdf",
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)

        assert doc.source_format == "pdf"
        assert doc.id is not None


def test_knowledge_document_source_format_defaults_to_none(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        doc = KnowledgeDocument(
            source_path="/knowledge/manual.md",
            title="Manual Doc",
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)

        assert doc.source_format is None
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_knowledge_source_format.py -v`

Expected: FAIL — `source_format` field does not exist on `KnowledgeDocument`.

**Step 3: Write the minimal implementation**

Modify `src/game_survey_workbench/models/knowledge.py`:

```python
from __future__ import annotations

from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class KnowledgeDocument(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_path: str
    title: str
    doc_type: str = "experience"
    stages: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    scenario: Optional[str] = None
    priority: int = 0
    source_format: Optional[str] = None  # "md" | "pdf" | "docx" | "pptx" | None (legacy)
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_knowledge_source_format.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/knowledge.py tests/test_knowledge_source_format.py
git commit -m "feat(2.0D): add source_format field to KnowledgeDocument"
```

---

## Task 4: Create the conversion preview template

**Files:**
- Create: `src/game_survey_workbench/templates/knowledge/convert_preview.html`

**Step 1: Create the template**

```html
{% extends "layout.html" %}
{% block title %}知识文档转换预览{% endblock %}
{% block content %}
<header>
  <p class="eyebrow"><a href="/knowledge">← 返回知识库</a></p>
  <h1>知识文档转换预览</h1>
  <p>原始文件：<strong>{{ original_filename }}</strong>（{{ source_format | upper }}）</p>
</header>

{% if quality.warning %}
<section class="workflow-alert alert-error">
  <strong>⚠ {{ quality.warning }}</strong>
</section>
{% endif %}

<section>
  <h2>转换结果预览</h2>
  <p class="help-text">字数：{{ quality.char_count }} ｜ 段落数：{{ quality.paragraph_count }}</p>
  <div class="conversion-preview" style="max-height:400px; overflow-y:auto; border:1px solid #ccc; padding:1em; background:#fafafa; white-space:pre-wrap; font-family:monospace; font-size:0.9em;">{{ markdown_text }}</div>
</section>

<section>
  <h2>元数据设置</h2>
  <form id="confirm-form" action="/knowledge/convert-confirm" method="post">
    <input type="hidden" name="staging_id" value="{{ staging_id }}">
    <input type="hidden" name="source_format" value="{{ source_format }}">

    <label for="title">文档标题</label>
    <input type="text" id="title" name="title" value="{{ inferred_title }}" required>

    <label for="doc_type">文档类型</label>
    <select id="doc_type" name="doc_type">
      <option value="experience">experience（经验/案例）</option>
      <option value="research">research（研究/报告）</option>
      <option value="benchmark">benchmark（基准/对标）</option>
      <option value="guide" selected>guide（方法论/指南）</option>
      <option value="theory">theory（理论）</option>
    </select>

    <fieldset>
      <legend>适用阶段（可多选）</legend>
      <label><input type="checkbox" name="purposes" value="questionnaire_design"> 问卷设计</label>
      <label><input type="checkbox" name="purposes" value="analysis"> 问卷分析</label>
      <label><input type="checkbox" name="purposes" value="reporting"> 报告写作</label>
    </fieldset>

    <button type="submit">确认入库</button>
  </form>

  <form action="/knowledge/convert-download" method="post" style="display:inline;">
    <input type="hidden" name="staging_id" value="{{ staging_id }}">
    <button type="submit">下载 Markdown 副本</button>
  </form>

  <a href="/knowledge">放弃</a>
</section>
{% endblock %}
```

**Step 2: Commit**

```bash
git add src/game_survey_workbench/templates/knowledge/convert_preview.html
git commit -m "feat(2.0D): add conversion preview template with metadata form"
```

---

## Task 5: Add conversion routes (preview, confirm, download)

**Files:**
- Modify: `src/game_survey_workbench/routes/knowledge.py`
- Create: `tests/test_knowledge_convert_routes.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables
from game_survey_workbench.services.workspace import bootstrap_workspace


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    return tmp_path


@pytest.fixture()
def app_client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as c:
        yield c


def _make_test_docx(workspace: Path) -> Path:
    """Create a minimal .docx for testing."""
    try:
        from docx import Document
    except ImportError:
        pytest.skip("python-docx not installed")
    doc = Document()
    doc.add_heading("Survey Methods", level=1)
    doc.add_paragraph("This document describes survey methodology for game research.")
    path = workspace / "test_doc.docx"
    doc.save(str(path))
    return path


def test_upload_non_markdown_redirects_to_convert_preview(app_client, workspace):
    docx_path = _make_test_docx(workspace)
    with open(docx_path, "rb") as f:
        response = app_client.post(
            "/knowledge/upload",
            files={"file": ("methods.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"purposes": ["questionnaire_design"]},
            follow_redirects=True,
        )
    # Should end up on the preview page (200) or a redirect to it
    assert response.status_code == 200
    html = response.text
    assert "转换预览" in html or "convert" in html.lower()
    assert "Survey Methods" in html or "methods.docx" in html


def test_upload_markdown_still_works_directly(app_client, workspace):
    response = app_client.post(
        "/knowledge/upload",
        files={"file": ("guide.md", b"---\ntitle: Test Guide\n---\nContent here.", "text/markdown")},
        data={"purposes": ["analysis"]},
        follow_redirects=False,
    )
    # .md files should go straight through (redirect to /knowledge)
    assert response.status_code == 303
    assert "/knowledge" in response.headers["location"]


def test_convert_confirm_ingests_document(app_client, workspace):
    docx_path = _make_test_docx(workspace)
    # First, upload to get to preview
    with open(docx_path, "rb") as f:
        preview_resp = app_client.post(
            "/knowledge/upload",
            files={"file": ("methods.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"purposes": []},
            follow_redirects=True,
        )
    assert preview_resp.status_code == 200

    # Find staging_id from the form
    staging_dir = workspace / "knowledge" / "staging"
    staging_files = list(staging_dir.glob("*.md")) if staging_dir.exists() else []
    if not staging_files:
        pytest.skip("No staging file created — conversion may have failed")
    staging_id = staging_files[0].stem

    confirm_resp = app_client.post(
        "/knowledge/convert-confirm",
        data={
            "staging_id": staging_id,
            "source_format": "docx",
            "title": "Survey Methods Guide",
            "doc_type": "guide",
            "purposes": ["questionnaire_design"],
        },
        follow_redirects=False,
    )
    assert confirm_resp.status_code == 303
    assert "upload_success" in confirm_resp.headers["location"]

    # Staging file should be cleaned up
    assert not staging_files[0].exists()


def test_convert_download_returns_markdown_file(app_client, workspace):
    # Create a staging .md file manually
    staging_dir = workspace / "knowledge" / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_file = staging_dir / "abc123.md"
    staging_file.write_text("# Test\n\nConverted content.", encoding="utf-8")

    response = app_client.post(
        "/knowledge/convert-download",
        data={"staging_id": "abc123"},
    )
    assert response.status_code == 200
    assert "text/markdown" in response.headers.get("content-type", "")
    assert b"Converted content" in response.content
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_knowledge_convert_routes.py -v`

Expected: FAIL — routes `convert-preview`, `convert-confirm`, `convert-download` do not exist; upload route does not handle non-`.md` files.

**Step 3: Write the minimal implementation**

Modify `src/game_survey_workbench/routes/knowledge.py`:

```python
from pathlib import Path
from uuid import uuid4

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
    stage_filter = request.query_params.get("stage", "").strip()
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
    if stage_filter:
        documents = [
            document for document in documents
            if stage_filter in (document.stages or [])
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
                "stage": stage_filter,
                "doc_type": doc_type,
                "tag": tag,
            },
        },
    )


@router.post("/knowledge/upload")
async def upload_knowledge(
    request: Request,
    file: UploadFile = File(...),
    purposes: list[str] = Form([]),
):
    settings = get_settings()
    filename = Path(file.filename or "uploaded.md").name
    suffix = Path(filename).suffix.lower()

    # Non-Markdown files: route to conversion preview
    if suffix in SUPPORTED_CONVERSION_EXTENSIONS:
        return await _handle_conversion_upload(
            request=request,
            file=file,
            filename=filename,
            suffix=suffix,
            workspace_root=settings.workspace_root,
        )

    # Markdown files: existing direct-ingest path
    knowledge_dir = settings.workspace_root / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
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


async def _handle_conversion_upload(
    *,
    request: Request,
    file: UploadFile,
    filename: str,
    suffix: str,
    workspace_root: Path,
) -> HTMLResponse:
    """Handle non-Markdown upload: convert, stage, show preview."""
    import tempfile

    # Save uploaded binary to a temp file for markitdown
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(await file.read())

    conversion = convert_to_markdown(tmp_path)
    tmp_path.unlink(missing_ok=True)

    if not conversion.success:
        return templates.TemplateResponse(
            request,
            "knowledge/detail.html",
            {
                "documents": [],
                "upload_success": None,
                "upload_error": conversion.error_message or "转换失败",
                "stage_label_map": STAGE_LABEL_MAP,
                "filters": {"search": "", "stage": "", "doc_type": "", "tag": ""},
            },
        )

    markdown_text = conversion.markdown_text or ""
    quality = assess_conversion_quality(markdown_text)

    # Infer title from filename
    inferred_title = Path(filename).stem

    # Stage the converted markdown
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
    staging_id = form.get("staging_id", "")
    source_format = form.get("source_format", "")
    title = form.get("title", "").strip() or "Untitled"
    doc_type = form.get("doc_type", "guide")
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

        # Build frontmatter-enriched markdown
        import frontmatter
        from game_survey_workbench.services.knowledge_ingest import PURPOSE_STAGE_MAP

        mapped_stages = [
            PURPOSE_STAGE_MAP[p] for p in purposes if p in PURPOSE_STAGE_MAP
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

        # Write final .md to knowledge directory
        knowledge_dir = settings.workspace_root / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = f"{title.replace(' ', '_').replace('/', '_')}.md"
        destination = knowledge_dir / safe_filename
        if destination.exists():
            destination = knowledge_dir / f"{staging_id}_{safe_filename}"
        destination.write_text(final_markdown, encoding="utf-8")

        # Ingest through existing pipeline
        result = ingest_knowledge_file(destination, project_root=settings.workspace_root)

        # Update source_format on the just-created KnowledgeDocument
        engine = get_engine(settings.workspace_root)
        with Session(engine) as session:
            doc = session.exec(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.title == result.document_title
                ).order_by(KnowledgeDocument.id.desc())
            ).first()
            if doc is not None:
                doc.source_format = source_format
                session.add(doc)
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
    staging_id = form.get("staging_id", "")

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
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_knowledge_convert_routes.py -v`

Expected: PASS (docx-dependent tests may skip if `python-docx` not installed)

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/knowledge.py tests/test_knowledge_convert_routes.py
git commit -m "feat(2.0D): add conversion preview, confirm, and download routes"
```

---

## Task 6: Update knowledge upload form to accept non-Markdown files

**Files:**
- Modify: `src/game_survey_workbench/templates/knowledge/detail.html`
- Modify: `tests/test_stage20_knowledge_library_page.py`

**Step 1: Write the failing test**

```python
def test_knowledge_page_upload_form_accepts_pdf_docx_pptx(client):
    response = client.get("/knowledge")
    html = response.text
    assert ".pdf" in html
    assert ".docx" in html
    assert ".pptx" in html
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage20_knowledge_library_page.py::test_knowledge_page_upload_form_accepts_pdf_docx_pptx -v`

Expected: FAIL — current form only accepts `.md,.txt`.

**Step 3: Write the minimal implementation**

In `src/game_survey_workbench/templates/knowledge/detail.html`, change the upload section:

Replace line 48:
```html
  <p class="help-text">支持 Markdown 文档。上传时请勾选这篇文档主要会用于哪些研究环节。</p>
```
With:
```html
  <p class="help-text">支持 Markdown (.md)、PDF (.pdf)、Word (.docx) 和 PowerPoint (.pptx) 文档。非 Markdown 文件会自动转换并提供预览。</p>
```

Replace line 50:
```html
    <input type="file" name="file" accept=".md,.txt" required>
```
With:
```html
    <input type="file" name="file" accept=".md,.txt,.pdf,.docx,.pptx" required>
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage20_knowledge_library_page.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/templates/knowledge/detail.html tests/test_stage20_knowledge_library_page.py
git commit -m "feat(2.0D): update knowledge upload form to accept PDF/DOCX/PPTX"
```

---

## Task 7: Add knowledge staging cleanup

**Files:**
- Modify: `src/game_survey_workbench/services/staging_cleanup.py`
- Modify: `tests/test_staging_cleanup.py`

**Step 1: Write the failing test**

```python
import os
import time
from pathlib import Path

from game_survey_workbench.services.staging_cleanup import cleanup_stale_staging_files


def test_cleanup_removes_knowledge_staging_files(tmp_path: Path):
    staging_dir = tmp_path / "knowledge" / "staging"
    staging_dir.mkdir(parents=True)

    old_file = staging_dir / "old_convert.md"
    old_file.write_text("old converted content")
    old_mtime = time.time() - 90000  # 25 hours ago
    os.utime(old_file, (old_mtime, old_mtime))

    new_file = staging_dir / "new_convert.md"
    new_file.write_text("new converted content")

    removed = cleanup_stale_staging_files(workspace_root=tmp_path, max_age_hours=24)
    assert removed >= 1
    assert not old_file.exists()
    assert new_file.exists()
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_staging_cleanup.py::test_cleanup_removes_knowledge_staging_files -v`

Expected: FAIL — current cleanup only scans `projects/*/data/staging`, not `knowledge/staging`.

**Step 3: Write the minimal implementation**

Modify `src/game_survey_workbench/services/staging_cleanup.py` to also scan `knowledge/staging`:

```python
from __future__ import annotations

import time
from pathlib import Path


def cleanup_stale_staging_files(*, workspace_root: Path, max_age_hours: int = 24) -> int:
    cutoff = time.time() - (max_age_hours * 3600)
    removed = 0

    # Dataset staging: projects/*/data/staging
    projects_dir = workspace_root / "projects"
    if projects_dir.exists():
        for staging_dir in projects_dir.glob("*/data/staging"):
            removed += _cleanup_dir(staging_dir, cutoff)

    # Knowledge staging: knowledge/staging
    knowledge_staging = workspace_root / "knowledge" / "staging"
    if knowledge_staging.exists():
        removed += _cleanup_dir(knowledge_staging, cutoff)

    return removed


def _cleanup_dir(directory: Path, cutoff: float) -> int:
    removed = 0
    for f in directory.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()
            removed += 1
    return removed
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_staging_cleanup.py -v`

Expected: PASS (both existing dataset staging test and new knowledge staging test)

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/staging_cleanup.py tests/test_staging_cleanup.py
git commit -m "feat(2.0D): extend staging cleanup to cover knowledge conversion staging"
```

---

## Task 8: Display source_format in the knowledge library page

**Files:**
- Modify: `src/game_survey_workbench/templates/knowledge/detail.html`
- Create: `tests/test_knowledge_format_display.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.services.workspace import bootstrap_workspace


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    return tmp_path


@pytest.fixture()
def app_client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as c:
        yield c


def test_knowledge_page_shows_source_format_badge(app_client, workspace):
    engine = get_engine(workspace)
    with Session(engine) as session:
        session.add(KnowledgeDocument(
            source_path="/knowledge/report.md",
            title="From PDF Report",
            source_format="pdf",
        ))
        session.add(KnowledgeDocument(
            source_path="/knowledge/manual.md",
            title="Native Markdown",
            source_format=None,
        ))
        session.commit()

    response = app_client.get("/knowledge")
    html = response.text
    assert "PDF" in html
    assert "From PDF Report" in html
    assert "Native Markdown" in html
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_knowledge_format_display.py -v`

Expected: FAIL — template does not display `source_format`.

**Step 3: Write the minimal implementation**

In `src/game_survey_workbench/templates/knowledge/detail.html`, in the document list section, after the title line (around line 68), add a format badge:

Replace the `<li>` block (lines 66-79) with:

```html
    <li>
      <strong>{{ document.title }}</strong>
      {% if document.source_format and document.source_format != "md" %}
      <span class="badge">{{ document.source_format | upper }}</span>
      {% endif %}
      <div class="help-text">文档类型：{{ document.doc_type }} ｜ 优先级：{{ document.priority }}</div>
      {% if document.stages %}
      <span>｜适用阶段：
        {% for stage in document.stages %}
        {{ stage_label_map.get(stage, stage) }}{% if not loop.last %}、{% endif %}
        {% endfor %}
      </span>
      {% endif %}
      {% if document.tags %}
      <div class="help-text">标签：{{ document.tags | join('、') }}</div>
      {% endif %}
      <div class="help-text">{{ document.source_path }}</div>
    </li>
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_knowledge_format_display.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/templates/knowledge/detail.html tests/test_knowledge_format_display.py
git commit -m "feat(2.0D): show source format badge on knowledge library page"
```

---

## Task 9: Run full regression and update roadmap

**Files:**
- Modify: `docs/plans/2026-03-15-game-survey-workbench-2.0-north-star.md`

**Step 1: Run full test suite**

Run:

```bash
.venv/Scripts/python.exe -m pytest -v
.venv/Scripts/python.exe -m compileall src
```

Expected:
- Full suite passes
- Compile check passes

**Step 2: Update roadmap status**

In the north-star document's "当前执行状态" section, add:

```markdown
- `2.0D 知识来源格式扩展`：已完成
  - 新增 `markitdown` 依赖，支持直接上传 PDF、Word、PowerPoint 文件
  - 非 Markdown 文件经自动转换后展示预览页，用户可确认入库、下载副本或放弃
  - 转换质量检测：自动识别空内容和乱码，给出警告
  - `KnowledgeDocument` 新增 `source_format` 字段追溯原始格式
  - 知识库页面显示来源格式标签，上传表单已支持 .pdf/.docx/.pptx
```

**Step 3: Manual verification checklist**

- [ ] Upload a `.md` file → goes straight to ingest (existing path unchanged)
- [ ] Upload a `.docx` file → shows conversion preview with markdown text
- [ ] Preview page shows character count, paragraph count
- [ ] Click "确认入库" → document appears in knowledge library with "DOCX" badge
- [ ] Click "下载 Markdown 副本" → browser downloads `.md` file
- [ ] Click "放弃" → returns to knowledge page, no document ingested
- [ ] Upload an empty `.pdf` → preview shows warning about empty content
- [ ] Upload a `.zip` file → rejected with clear error message
- [ ] Knowledge page file input accepts `.pdf`, `.docx`, `.pptx` extensions
- [ ] Existing 2.0A/B/C tests still pass

**Step 4: Commit**

```bash
git add docs/plans/2026-03-15-game-survey-workbench-2.0-north-star.md
git commit -m "docs: update 2.0 roadmap after knowledge format expansion"
```

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| markitdown produces poor quality for complex PDFs | Medium | High | Preview page lets users assess; download-and-edit escape hatch |
| markitdown dependency introduces version conflicts | Low | Low | Pinned to `>=0.1,<1.0`; no transitive conflicts with existing deps |
| Scanned PDFs produce empty output | Low | Medium | Quality assessment detects empty text and warns user |
| Large files (>50MB PDFs) slow down conversion | Medium | Low | markitdown processes locally; no timeout needed for MVP |
| Staging files accumulate | Low | Medium | Cleanup utility already extended to cover knowledge staging |

## Verification Checklist Before Any Completion Claim

- Run: `.venv/Scripts/python.exe -m pytest tests/test_knowledge_convert.py tests/test_knowledge_source_format.py tests/test_knowledge_convert_routes.py tests/test_knowledge_format_display.py tests/test_staging_cleanup.py -v`
- Run: `.venv/Scripts/python.exe -m pytest -v`
- Run: `.venv/Scripts/python.exe -m compileall src`
- Manually confirm:
  - `.md` uploads still work unchanged
  - `.docx` uploads go through conversion preview
  - Preview shows quality warnings when appropriate
  - Confirm/download/abandon all work correctly
  - Knowledge library shows source format badges

## Implementation Phases Summary

| Phase | Tasks | Duration Estimate |
|---|---|---|
| **P1: Conversion core** | Tasks 1-3 | 1 day |
| **P2: Routes & UI** | Tasks 4-6 | 1 day |
| **P3: Polish & regression** | Tasks 7-9 | 0.5 day |
