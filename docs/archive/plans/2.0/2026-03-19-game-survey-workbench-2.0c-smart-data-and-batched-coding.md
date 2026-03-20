# 2.0C Smart Data Tolerance & Batched Text Coding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the data import flow tolerant of non-dual-header CSV formats with a preview-and-confirm step, and make open-text coding robust at scale via batched LLM calls with progress tracking, failure recovery, and codebook merging.

**Architecture:** Extend the existing monolith. Phase 1 adds a format-detection layer upstream of `parse_dual_header_dataframe()` plus a preview-confirm two-step route. Phase 2 adds `CodingJob` / `CodingBatch` persistence models and rewires `code_open_text_column()` to split large response sets into serial batches with rolling codebook, then merge results. Phase 3 adds the codebook merge-review UI and wires batched coding into the existing insight generation flow.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, Jinja2, pandas, pytest, existing TF-IDF retrieval store, existing `LLMClient` protocol

---

## Assumptions

- `docs/plans/2026-03-15-game-survey-workbench-2.0-north-star.md` is the source of truth for 2.0 direction.
- 2.0A (global knowledge library) and 2.0B (layered retrieval) are complete and merged to master at commit `0eff228`.
- No 1.0 `knowledge_pack` backward compatibility is required — this is a 2.0-only plan.
- The existing `parse_dual_header_dataframe()` in `upload_contract.py` remains available as one of two parsing paths; it is not removed.
- `ALLOWED_TYPE_MARKERS` (`metadata`, `single_choice`, `multi_select`, `free_text`, `scale`, `matrix`, `ranking`) remain the canonical question type vocabulary.
- The existing `LLMClient` protocol (`generate(prompt: str) -> str`) is sufficient for batched calls; no streaming is introduced in this phase.

## Non-Goals

- **WebSocket / SSE real-time push** — polling at 3s interval is sufficient for progress.
- **Multi-question parallel coding** — batches for the same question run serially to maintain codebook consistency.
- **Excel-native import** — `.xlsx` / `.xls` already work via pandas; no special handling is added beyond what exists.
- **Manual single-response code editing UI** — users can only merge near-duplicate codes, not edit individual response assignments.
- **Embedding-based coding similarity** — codebook near-duplicate detection uses exact string matching only; semantic similarity is deferred.

## Dependencies

| Dependency | Status | Notes |
|---|---|---|
| 2.0A/2.0B merged to master | ✅ `0eff228` | `retrieve_project_knowledge()` with layered retrieval is available |
| `parse_dual_header_dataframe()` | ✅ Exists | `src/game_survey_workbench/services/upload_contract.py` |
| `code_open_text_column()` | ✅ Exists | `src/game_survey_workbench/services/text_coding.py` |
| `LLMClient` protocol | ✅ Exists | `src/game_survey_workbench/llm/client.py` |
| `DatasetRecord` model | ✅ Exists | `src/game_survey_workbench/models/dataset.py` |
| `CodingResult` model | ✅ Exists | `src/game_survey_workbench/models/text_coding.py` |

## Data Model Changes

### New Tables

```
CodingJob
├── id: int (PK)
├── project_slug: str (indexed)
├── analysis_run_id: str (indexed)
├── question_column: str
├── status: str  # queued | running | merging | done | partial | failed | cancelled
├── total_responses: int
├── coded_responses: int  # updated after each batch completes
├── batch_size: int
├── final_codebook_json: dict | None  # merged codebook after all batches
├── error_message: str | None
├── created_at: datetime
└── finished_at: datetime | None

CodingBatch
├── id: int (PK)
├── job_id: int (FK → CodingJob.id, indexed)
├── batch_index: int
├── status: str  # pending | running | done | failed
├── input_texts_json: list[str]  # deduplicated texts for this batch
├── output_codes_json: dict | None  # raw LLM coding output for this batch
├── retry_count: int (default 0)
└── error_message: str | None
```

### Existing Model Changes

`DatasetRecord` gains two optional fields:

- `format_type: str | None` — `"dual_header"` / `"single_header"` / `"auto_detected"`
- `column_overrides_json: dict | None` — user-confirmed column schema overrides from preview page

These are additive (nullable), so no migration is needed for existing rows.

## Route Changes

### Phase 1: Data Format Tolerance

| Route | Method | Replaces / New | Purpose |
|---|---|---|---|
| `/{slug}/datasets/upload-preview` | POST | Replaces first half of `import-form` | Save temp file, detect format, return preview page |
| `/{slug}/datasets/confirm-import` | POST | Replaces second half of `import-form` | Accept user-confirmed schema, import dataset |

The existing `POST /{slug}/datasets/import` JSON API route is kept unchanged for programmatic callers — it continues to require dual-header format.

### Phase 2: Batched Text Coding

| Route | Method | New | Purpose |
|---|---|---|---|
| `/{slug}/coding-jobs` | POST | ✓ | Create a coding job for one question column |
| `/{slug}/coding-jobs/{id}/status` | GET | ✓ | Poll progress (JSON) |
| `/{slug}/coding-jobs/{id}/cancel` | POST | ✓ | Cancel a running job |
| `/{slug}/coding-jobs/{id}/retry-failed` | POST | ✓ | Retry failed batches |

### Phase 3: Merge Review

| Route | Method | New | Purpose |
|---|---|---|---|
| `/{slug}/coding-jobs/{id}/merge-review` | GET | ✓ | Show near-duplicate codebook entries for user confirmation |
| `/{slug}/coding-jobs/{id}/merge-confirm` | POST | ✓ | Accept user merge decisions, finalize codebook |

## Error Handling

| Scenario | Behavior |
|---|---|
| File completely unreadable (not tabular, encoding broken) | `400` with explicit error message |
| Format readable but column type inference low-confidence | Return preview page with yellow warning per column, do not block |
| User confirms wrong column schema then re-uploads | Allowed; no side effects on existing data |
| Single coding batch LLM call fails | Auto-retry up to 2 times with exponential backoff; if still fails, mark batch `failed` |
| Coding job finishes with some failed batches | `status = partial`; user can retry failed batches or accept partial results |
| Coding job cancelled by user | Already-completed batches preserved; job can be resumed via retry |
| Codebook merge produces near-duplicate entries | Shown to user for manual resolution; exact duplicates auto-merged |

---

## Task 1: Add `detect_format()` and single-header inference to upload_contract

**Files:**
- Modify: `src/game_survey_workbench/services/upload_contract.py`
- Create: `tests/test_format_detection.py`

**Step 1: Write the failing tests**

```python
import pandas as pd
from pathlib import Path

from game_survey_workbench.services.upload_contract import (
    detect_format,
    FormatDetectionResult,
    ALLOWED_TYPE_MARKERS,
)


def test_detect_format_identifies_dual_header_csv(tmp_path: Path):
    csv = tmp_path / "dual.csv"
    csv.write_text(
        "Q1,Q2,Q3\n"
        "single_choice,free_text,scale\n"
        "A,hello,5\n"
        "B,world,3\n",
        encoding="utf-8",
    )
    result = detect_format(csv)
    assert result.format_type == "dual_header"
    assert result.column_titles == ["Q1", "Q2", "Q3"]
    assert result.column_types == ["single_choice", "free_text", "scale"]


def test_detect_format_identifies_single_header_csv(tmp_path: Path):
    csv = tmp_path / "single.csv"
    csv.write_text(
        "Q1,Q2,Q3\n"
        "Male,I love this game,5\n"
        "Female,Great graphics,3\n"
        "Male,Fun gameplay,4\n",
        encoding="utf-8",
    )
    result = detect_format(csv)
    assert result.format_type == "single_header"
    assert result.column_titles == ["Q1", "Q2", "Q3"]
    assert len(result.inferred_columns) == 3
    for col in result.inferred_columns:
        assert col.inferred_type in ALLOWED_TYPE_MARKERS
        assert col.confidence in ("high", "medium", "low")
        assert col.reason  # non-empty string


def test_detect_format_recognizes_wenjuanxing_multi_select_header(tmp_path: Path):
    csv = tmp_path / "wjx.csv"
    csv.write_text(
        "你最喜欢的功能是什么（多选）,你的建议（填空）\n"
        "A;B;C,很好\n"
        "A;D,还行\n",
        encoding="utf-8",
    )
    result = detect_format(csv)
    assert result.format_type == "single_header"
    assert result.inferred_columns[0].inferred_type == "multi_select"
    assert result.inferred_columns[1].inferred_type == "free_text"


def test_detect_format_raises_on_unreadable_file(tmp_path: Path):
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\x80\x81\x82")
    import pytest
    with pytest.raises(ValueError, match="Unsupported|cannot"):
        detect_format(bad)
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_format_detection.py -v`

Expected: FAIL — `detect_format`, `FormatDetectionResult` do not exist yet.

**Step 3: Write the minimal implementation**

Add to `src/game_survey_workbench/services/upload_contract.py`:

```python
from dataclasses import dataclass


@dataclass
class InferredColumn:
    title: str
    inferred_type: str
    confidence: str  # "high" | "medium" | "low"
    reason: str


@dataclass
class FormatDetectionResult:
    format_type: str  # "dual_header" | "single_header"
    column_titles: list[str]
    column_types: list[str]  # populated for dual_header
    inferred_columns: list[InferredColumn]  # populated for single_header
    preview_rows: list[list[str]]  # first 5 data rows for preview


# Platform-specific header keyword rules
HEADER_KEYWORD_RULES: list[tuple[str, str, str]] = [
    # (keyword_substring, inferred_type, reason)
    ("（多选）", "multi_select", "Header contains 问卷星 multi-select marker '（多选）'"),
    ("（填空）", "free_text", "Header contains 问卷星 free-text marker '（填空）'"),
    ("(多选)", "multi_select", "Header contains multi-select marker '(多选)'"),
    ("(填空)", "free_text", "Header contains free-text marker '(填空)'"),
    ("multiple choices", "multi_select", "Header contains 'Multiple Choices'"),
    ("open-ended response", "free_text", "Header contains SurveyMonkey 'Open-Ended Response'"),
    ("feel free", "free_text", "Header contains 'feel free' suggesting open text"),
    ("suggestion", "free_text", "Header contains 'suggestion' suggesting open text"),
]


def detect_format(path: Path) -> FormatDetectionResult:
    raw = _load_raw_tabular_file(path)
    if len(raw.index) < 2:
        raise ValueError("File has fewer than 2 rows; cannot detect format.")

    column_titles = raw.iloc[0].fillna("").astype(str).tolist()
    candidate_types = raw.iloc[1].fillna("").astype(str).str.strip().tolist()

    if all(marker in ALLOWED_TYPE_MARKERS for marker in candidate_types):
        # Dual-header format
        data_rows = raw.iloc[2:]
        preview = data_rows.head(5).fillna("").astype(str).values.tolist()
        return FormatDetectionResult(
            format_type="dual_header",
            column_titles=column_titles,
            column_types=candidate_types,
            inferred_columns=[],
            preview_rows=preview,
        )

    # Single-header format — infer types
    data_rows = raw.iloc[1:]
    data_rows.columns = column_titles
    data_rows = data_rows.reset_index(drop=True)
    preview = data_rows.head(5).fillna("").astype(str).values.tolist()

    inferred: list[InferredColumn] = []
    for col_name in column_titles:
        series = data_rows[col_name]
        col_type, confidence, reason = _infer_column_type(col_name, series)
        inferred.append(InferredColumn(
            title=col_name,
            inferred_type=col_type,
            confidence=confidence,
            reason=reason,
        ))

    return FormatDetectionResult(
        format_type="single_header",
        column_titles=column_titles,
        column_types=[c.inferred_type for c in inferred],
        inferred_columns=inferred,
        preview_rows=preview,
    )


def _infer_column_type(header: str, series: pd.Series) -> tuple[str, str, str]:
    """Return (type, confidence, reason) for a single column."""
    # 1. Check header keyword rules first
    lowered = header.lower()
    for keyword, col_type, reason in HEADER_KEYWORD_RULES:
        if keyword.lower() in lowered:
            return col_type, "high", reason

    # 2. Fall back to data heuristics
    from game_survey_workbench.services.dataset_import import (
        _separator_density,
        _numeric_density,
        _average_text_length,
    )

    sep_density = _separator_density(series)
    if sep_density >= 0.5:
        return "multi_select", "high", f"Separator density {sep_density:.0%} >= 50%"

    num_density = _numeric_density(series)
    if num_density >= 0.8:
        return "scale", "high", f"Numeric density {num_density:.0%} >= 80%"

    avg_len = _average_text_length(series)
    if avg_len >= 25 and num_density < 0.3:
        return "free_text", "medium", f"Average text length {avg_len:.0f} chars, low numeric density"

    unique_ratio = series.dropna().nunique() / max(len(series.dropna()), 1)
    if unique_ratio <= 0.3:
        return "single_choice", "medium", f"Low unique ratio {unique_ratio:.0%} suggests categorical"

    return "single_choice", "low", "Default fallback — could not determine type with confidence"
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_format_detection.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/upload_contract.py tests/test_format_detection.py
git commit -m "feat(2.0C): add format detection with dual-header and single-header inference"
```

---

## Task 2: Add preview-confirm two-step import routes and template

**Files:**
- Modify: `src/game_survey_workbench/routes/datasets.py`
- Create: `src/game_survey_workbench/templates/datasets/preview.html`
- Modify: `src/game_survey_workbench/services/dataset_import.py`
- Modify: `src/game_survey_workbench/models/dataset.py`
- Create: `tests/test_upload_preview.py`

**Step 1: Write the failing tests**

```python
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.workspace import bootstrap_workspace


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)
    return tmp_path


@pytest.fixture()
def app_client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as c:
        yield c


def _make_single_header_csv(workspace: Path) -> Path:
    csv = workspace / "test_upload.csv"
    csv.write_text(
        "Gender,Feedback,Rating\n"
        "Male,Great game,5\n"
        "Female,Needs improvement,3\n"
        "Male,Love the graphics,4\n",
        encoding="utf-8",
    )
    return csv


def test_upload_preview_returns_preview_page_for_single_header(app_client, workspace):
    csv = _make_single_header_csv(workspace)
    with open(csv, "rb") as f:
        response = app_client.post(
            "/projects/demo/datasets/upload-preview",
            files={"file": ("test.csv", f, "text/csv")},
        )
    assert response.status_code == 200
    html = response.text
    assert "预览" in html or "Preview" in html
    assert "Gender" in html
    assert "Feedback" in html


def test_upload_preview_returns_preview_page_for_dual_header(app_client, workspace):
    csv = workspace / "dual.csv"
    csv.write_text(
        "Gender,Feedback,Rating\n"
        "single_choice,free_text,scale\n"
        "Male,Great,5\n",
        encoding="utf-8",
    )
    with open(csv, "rb") as f:
        response = app_client.post(
            "/projects/demo/datasets/upload-preview",
            files={"file": ("dual.csv", f, "text/csv")},
        )
    assert response.status_code == 200
    html = response.text
    assert "Gender" in html


def test_confirm_import_creates_dataset_and_redirects(app_client, workspace):
    csv = _make_single_header_csv(workspace)
    with open(csv, "rb") as f:
        preview_resp = app_client.post(
            "/projects/demo/datasets/upload-preview",
            files={"file": ("test.csv", f, "text/csv")},
        )
    assert preview_resp.status_code == 200

    # Extract staging_id from hidden form field (simplified — in real test parse HTML)
    # For this test, find the staging file directly
    staging_dir = workspace / "projects" / "demo" / "data" / "staging"
    staging_files = list(staging_dir.glob("*.csv"))
    assert len(staging_files) == 1
    staging_id = staging_files[0].stem

    response = app_client.post(
        "/projects/demo/datasets/confirm-import",
        data={
            "staging_id": staging_id,
            "column_types": ["single_choice", "free_text", "scale"],
            "column_include": ["Gender", "Feedback", "Rating"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/analysis/" in response.headers["location"]

    # Staging file should be cleaned up
    assert not staging_files[0].exists()


def test_upload_preview_rejects_unreadable_file(app_client, workspace):
    bad = workspace / "bad.bin"
    bad.write_bytes(b"\x00\x01\x02")
    with open(bad, "rb") as f:
        response = app_client.post(
            "/projects/demo/datasets/upload-preview",
            files={"file": ("bad.bin", f, "application/octet-stream")},
        )
    assert response.status_code in (400, 303)
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_upload_preview.py -v`

Expected: FAIL — routes `upload-preview` and `confirm-import` do not exist.

**Step 3: Write the minimal implementation**

Add to `src/game_survey_workbench/routes/datasets.py`:

```python
@router.post("/projects/{project_slug}/datasets/upload-preview", response_class=HTMLResponse)
async def upload_preview(project_slug: str, request: Request, file: UploadFile = File(...)):
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

    # Save to staging
    staging_dir = settings.workspace_root / "projects" / project_slug / "data" / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_id = uuid4().hex[:12]
    staging_path = staging_dir / f"{staging_id}{suffix}"
    staging_path.write_bytes(await file.read())

    try:
        from game_survey_workbench.services.upload_contract import detect_format
        detection = detect_format(staging_path)
    except ValueError as exc:
        staging_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return templates.TemplateResponse(request, "datasets/preview.html", {
        "project_slug": project_slug,
        "staging_id": staging_id,
        "detection": detection,
    })


@router.post("/projects/{project_slug}/datasets/confirm-import")
async def confirm_import(project_slug: str, request: Request):
    settings = get_settings()
    form = await request.form()
    staging_id = form.get("staging_id")
    column_types = form.getlist("column_types")
    column_include = form.getlist("column_include")

    staging_dir = settings.workspace_root / "projects" / project_slug / "data" / "staging"
    staging_path = next(staging_dir.glob(f"{staging_id}.*"), None)
    if staging_path is None or not staging_path.exists():
        raise HTTPException(status_code=400, detail="Staging file not found or expired")

    try:
        dataset = import_dataset_with_overrides(
            csv_path=staging_path,
            project_slug=project_slug,
            workspace_root=settings.workspace_root,
            column_types=column_types,
            column_include=column_include,
        )
    except ValueError as exc:
        return RedirectResponse(
            url=f"/projects/{project_slug}?upload_error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    finally:
        staging_path.unlink(missing_ok=True)

    return RedirectResponse(
        url=f"/projects/{project_slug}/analysis/{dataset.analysis_run_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
```

Add `import_dataset_with_overrides()` to `src/game_survey_workbench/services/dataset_import.py`:

```python
def import_dataset_with_overrides(
    csv_path: Path,
    *,
    project_slug: str,
    workspace_root: Path,
    column_types: list[str],
    column_include: list[str],
) -> ImportedDataset:
    """Import a dataset using user-confirmed column types from the preview page."""
    bootstrap_workspace(workspace_root)
    create_db_and_tables(workspace_root)
    from game_survey_workbench.services.upload_contract import detect_format
    detection = detect_format(csv_path)

    # Build dataframe from detected format
    raw = _load_tabular_file(csv_path, header=None)
    if detection.format_type == "dual_header":
        column_titles = raw.iloc[0].fillna("").astype(str).tolist()
        dataframe = raw.iloc[2:].copy()
    else:
        column_titles = raw.iloc[0].fillna("").astype(str).tolist()
        dataframe = raw.iloc[1:].copy()
    dataframe.columns = column_titles
    dataframe = dataframe.reset_index(drop=True)

    # Apply user overrides
    question_columns: dict[str, QuestionColumnSchema] = {}
    for i, col_name in enumerate(column_titles):
        if i >= len(column_types):
            break
        declared_type = column_types[i]
        if declared_type == "metadata" or col_name not in column_include:
            continue
        if classify_column(col_name) == "metadata":
            continue
        question_columns[col_name] = QuestionColumnSchema(
            column_role="question",
            question_type=declared_type,
            include_in_analysis=col_name in column_include,
        )

    # Move staging file to raw/
    stored_path = store_uploaded_dataset(
        source_path=csv_path,
        filename=csv_path.name,
        project_slug=project_slug,
        workspace_root=workspace_root,
    )

    dataset_id = str(uuid4())
    analysis_run_id = str(uuid4())

    schema_payload = {k: v.model_dump() for k, v in question_columns.items()}

    # Persist schema file
    schema_dir = workspace_root / "projects" / project_slug / "data" / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    schema_path = schema_dir / f"{dataset_id}.json"
    schema_path.write_text(json.dumps(schema_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    engine = get_engine(workspace_root)
    with Session(engine) as session:
        record = DatasetRecord(
            dataset_id=dataset_id,
            project_slug=project_slug,
            source_path=str(stored_path),
            dataset_schema=schema_payload,
            analysis_run_id=analysis_run_id,
        )
        session.add(record)
        session.add(AnalysisRunRecord(
            analysis_run_id=analysis_run_id,
            project_slug=project_slug,
            dataset_id=dataset_id,
            status="ready",
        ))
        session.commit()

    return ImportedDataset(
        dataset_id=dataset_id,
        project_slug=project_slug,
        source_path=str(stored_path),
        question_columns=question_columns,
        analysis_run_id=analysis_run_id,
    )
```

Create the preview template at `src/game_survey_workbench/templates/datasets/preview.html`:

```html
{% extends "layout.html" %}
{% block content %}
<h2>数据导入预览</h2>

<p>检测格式: <strong>{{ detection.format_type }}</strong></p>

<form method="post" action="/projects/{{ project_slug }}/datasets/confirm-import">
  <input type="hidden" name="staging_id" value="{{ staging_id }}">

  <table>
    <thead>
      <tr>
        <th>列名</th>
        <th>推断题型</th>
        <th>推断依据</th>
        <th>纳入分析</th>
      </tr>
    </thead>
    <tbody>
      {% for i in range(detection.column_titles | length) %}
      <tr>
        <td>{{ detection.column_titles[i] }}</td>
        <td>
          <select name="column_types">
            {% for t in ["metadata","single_choice","multi_select","free_text","scale","matrix","ranking"] %}
            <option value="{{ t }}"
              {% if detection.column_types[i] == t %}selected{% endif %}>
              {{ t }}
            </option>
            {% endfor %}
          </select>
        </td>
        <td>
          {% if detection.inferred_columns %}
            {{ detection.inferred_columns[i].reason }} ({{ detection.inferred_columns[i].confidence }})
          {% else %}
            双层表头声明
          {% endif %}
        </td>
        <td>
          <input type="checkbox" name="column_include" value="{{ detection.column_titles[i] }}" checked>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <h3>数据预览（前5行）</h3>
  <table>
    <thead>
      <tr>
        {% for title in detection.column_titles %}
        <th>{{ title }}</th>
        {% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for row in detection.preview_rows %}
      <tr>
        {% for cell in row %}
        <td>{{ cell }}</td>
        {% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <button type="submit">确认导入</button>
  <a href="/projects/{{ project_slug }}">返回重新上传</a>
</form>
{% endblock %}
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_upload_preview.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/datasets.py src/game_survey_workbench/templates/datasets/preview.html src/game_survey_workbench/services/dataset_import.py tests/test_upload_preview.py
git commit -m "feat(2.0C): add upload-preview and confirm-import two-step flow"
```

---

## Task 3: Update project detail template to route uploads through preview

**Files:**
- Modify: `src/game_survey_workbench/templates/projects/detail.html`
- Modify: `tests/test_stage5a_upload_forms.py`

**Step 1: Write the failing test**

```python
def test_project_page_upload_form_posts_to_upload_preview(client):
    response = client.get("/projects/demo")
    html = response.text
    assert 'action="/projects/demo/datasets/upload-preview"' in html
    assert 'action="/projects/demo/datasets/import-form"' not in html
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage5a_upload_forms.py::test_project_page_upload_form_posts_to_upload_preview -v`

Expected: FAIL — the form still posts to `import-form`.

**Step 3: Write the minimal implementation**

In `templates/projects/detail.html`, change the upload form action from:

```html
action="/projects/{{ project.slug }}/datasets/import-form"
```

to:

```html
action="/projects/{{ project.slug }}/datasets/upload-preview"
```

Keep the `import-form` route in the codebase for backward compatibility but it is no longer the primary UI path.

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stage5a_upload_forms.py -v`

Expected: PASS (may need to update other assertions in this test file that check for the old route)

**Step 5: Commit**

```bash
git add src/game_survey_workbench/templates/projects/detail.html tests/test_stage5a_upload_forms.py
git commit -m "feat(2.0C): route project upload form through preview page"
```

---

## Task 4: Add CodingJob and CodingBatch persistence models

**Files:**
- Create: `src/game_survey_workbench/models/coding_job.py`
- Modify: `src/game_survey_workbench/db.py`
- Create: `tests/test_coding_job_model.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

from sqlmodel import Session

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.coding_job import CodingJob, CodingBatch


def test_coding_job_and_batch_persist_and_load(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        job = CodingJob(
            project_slug="demo",
            analysis_run_id="run-1",
            question_column="Q1",
            status="queued",
            total_responses=100,
            coded_responses=0,
            batch_size=80,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        assert job.id is not None

        batch = CodingBatch(
            job_id=job.id,
            batch_index=0,
            status="pending",
            input_texts_json=["resp1", "resp2"],
        )
        session.add(batch)
        session.commit()
        session.refresh(batch)
        assert batch.id is not None
        assert batch.job_id == job.id


def test_coding_job_status_transitions(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        job = CodingJob(
            project_slug="demo",
            analysis_run_id="run-1",
            question_column="Q1",
            status="queued",
            total_responses=50,
            coded_responses=0,
            batch_size=80,
        )
        session.add(job)
        session.commit()

        job.status = "running"
        job.coded_responses = 25
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.status == "running"
        assert job.coded_responses == 25
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_coding_job_model.py -v`

Expected: FAIL — `CodingJob` and `CodingBatch` do not exist.

**Step 3: Write the minimal implementation**

Create `src/game_survey_workbench/models/coding_job.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class CodingJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_slug: str = Field(index=True)
    analysis_run_id: str = Field(index=True)
    question_column: str
    status: str = Field(default="queued")  # queued|running|merging|done|partial|failed|cancelled
    total_responses: int = 0
    coded_responses: int = 0
    batch_size: int = 80
    final_codebook_json: dict | None = Field(default=None, sa_column=Column(JSON))
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


class CodingBatch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(index=True)
    batch_index: int = 0
    status: str = Field(default="pending")  # pending|running|done|failed
    input_texts_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    output_codes_json: dict | None = Field(default=None, sa_column=Column(JSON))
    retry_count: int = 0
    error_message: str | None = None
```

Register the model in `src/game_survey_workbench/db.py` by adding:

```python
from game_survey_workbench.models import coding_job as _coding_job_models
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_coding_job_model.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/coding_job.py src/game_survey_workbench/db.py tests/test_coding_job_model.py
git commit -m "feat(2.0C): add CodingJob and CodingBatch persistence models"
```

---

## Task 5: Implement batched coding service with dedup, serial execution, and rolling codebook

**Files:**
- Create: `src/game_survey_workbench/services/batched_coding.py`
- Modify: `src/game_survey_workbench/llm/prompts/open_text_coding.md` (add batch-continuation variant)
- Create: `src/game_survey_workbench/llm/prompts/open_text_coding_continuation.md`
- Create: `tests/test_batched_coding.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path
from unittest.mock import MagicMock
import json

from game_survey_workbench.db import create_db_and_tables
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.batched_coding import (
    create_coding_job,
    run_coding_job,
    get_coding_job_status,
    deduplicate_responses,
)


def _fake_llm_response(themes=None):
    if themes is None:
        themes = [{"theme_name": "Positive", "count": 2, "example_responses": ["good", "great"]}]
    return json.dumps({"themes": themes, "uncoded_count": 0})


def test_deduplicate_responses_removes_exact_duplicates():
    unique, mapping = deduplicate_responses(["a", "b", "a", "c", "b", "a"])
    assert unique == ["a", "b", "c"]
    assert mapping["a"] == [0, 2, 5]
    assert mapping["b"] == [1, 4]
    assert mapping["c"] == [3]


def test_create_coding_job_splits_into_correct_number_of_batches(tmp_path: Path):
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)
    responses = [f"response {i}" for i in range(200)]
    job, batches = create_coding_job(
        workspace_root=tmp_path,
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        batch_size=80,
    )
    assert job.status == "queued"
    assert job.total_responses == 200
    assert len(batches) == 3  # ceil(200/80)
    assert all(b.status == "pending" for b in batches)


def test_small_dataset_creates_single_batch(tmp_path: Path):
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)
    responses = [f"response {i}" for i in range(50)]
    job, batches = create_coding_job(
        workspace_root=tmp_path,
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        batch_size=80,
    )
    assert len(batches) == 1


def test_run_coding_job_completes_all_batches(tmp_path: Path):
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)

    # Ingest minimal knowledge so retrieval doesn't fail
    from game_survey_workbench.services.workspace import bootstrap_workspace
    bootstrap_workspace(tmp_path)

    responses = [f"response {i}" for i in range(160)]
    mock_client = MagicMock()
    mock_client.generate.return_value = _fake_llm_response()

    job, batches = create_coding_job(
        workspace_root=tmp_path,
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        batch_size=80,
    )

    run_coding_job(
        workspace_root=tmp_path,
        job_id=job.id,
        client=mock_client,
    )

    status = get_coding_job_status(workspace_root=tmp_path, job_id=job.id)
    assert status["status"] == "done"
    assert status["completed_batches"] == 2
    assert status["total_batches"] == 2
    assert mock_client.generate.call_count == 2


def test_run_coding_job_handles_batch_failure_gracefully(tmp_path: Path):
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)
    from game_survey_workbench.services.workspace import bootstrap_workspace
    bootstrap_workspace(tmp_path)

    responses = [f"response {i}" for i in range(160)]
    mock_client = MagicMock()
    # First batch succeeds, second fails all retries
    mock_client.generate.side_effect = [
        _fake_llm_response(),
        Exception("API error"),
        Exception("API error"),
        Exception("API error"),
    ]

    job, _ = create_coding_job(
        workspace_root=tmp_path,
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        batch_size=80,
    )

    run_coding_job(
        workspace_root=tmp_path,
        job_id=job.id,
        client=mock_client,
    )

    status = get_coding_job_status(workspace_root=tmp_path, job_id=job.id)
    assert status["status"] == "partial"
    assert status["completed_batches"] == 1
    assert status["failed_batches"] == 1
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_batched_coding.py -v`

Expected: FAIL — `batched_coding` module does not exist.

**Step 3: Write the minimal implementation**

Create `src/game_survey_workbench/services/batched_coding.py`:

```python
from __future__ import annotations

import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.llm.client import LLMClient
from game_survey_workbench.models.coding_job import CodingBatch, CodingJob
from game_survey_workbench.services.text_coding import (
    build_coding_context,
    load_coding_prompt,
    parse_coding_response,
)
from game_survey_workbench.services.knowledge_ingest import retrieve_project_knowledge

DEFAULT_BATCH_SIZE = 80
MAX_RETRIES = 2


def deduplicate_responses(responses: list[str]) -> tuple[list[str], dict[str, list[int]]]:
    seen: dict[str, list[int]] = {}
    unique: list[str] = []
    for i, text in enumerate(responses):
        stripped = text.strip()
        if not stripped:
            continue
        if stripped in seen:
            seen[stripped].append(i)
        else:
            seen[stripped] = [i]
            unique.append(stripped)
    return unique, seen


def create_coding_job(
    *,
    workspace_root: Path,
    project_slug: str,
    analysis_run_id: str,
    question_column: str,
    responses: list[str],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[CodingJob, list[CodingBatch]]:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)

    unique, _mapping = deduplicate_responses(responses)
    num_batches = max(1, math.ceil(len(unique) / batch_size))

    job = CodingJob(
        project_slug=project_slug,
        analysis_run_id=analysis_run_id,
        question_column=question_column,
        status="queued",
        total_responses=len(unique),
        coded_responses=0,
        batch_size=batch_size,
    )

    with Session(engine) as session:
        session.add(job)
        session.commit()
        session.refresh(job)

        batches: list[CodingBatch] = []
        for idx in range(num_batches):
            start = idx * batch_size
            end = min(start + batch_size, len(unique))
            batch = CodingBatch(
                job_id=job.id,
                batch_index=idx,
                status="pending",
                input_texts_json=unique[start:end],
            )
            session.add(batch)
            batches.append(batch)
        session.commit()
        for b in batches:
            session.refresh(b)

    return job, batches


def run_coding_job(
    *,
    workspace_root: Path,
    job_id: int,
    client: LLMClient,
    top_k: int = 10,
) -> None:
    engine = get_engine(workspace_root)

    with Session(engine) as session:
        job = session.exec(select(CodingJob).where(CodingJob.id == job_id)).first()
        if job is None:
            raise ValueError(f"CodingJob {job_id} not found")
        job.status = "running"
        session.add(job)
        session.commit()

    # Retrieve knowledge once for the whole job
    snippets = retrieve_project_knowledge(
        workspace_root=workspace_root,
        project_slug=job.project_slug,
        query=job.question_column,
        stages=["analysis"],
        top_k=top_k,
    )

    prompt = load_coding_prompt()
    continuation_prompt = _load_continuation_prompt()
    rolling_codebook: list[dict] = []

    with Session(engine) as session:
        batches = session.exec(
            select(CodingBatch).where(CodingBatch.job_id == job_id)
        ).all()
        batches = sorted(batches, key=lambda b: b.batch_index)

    for batch in batches:
        _run_single_batch(
            engine=engine,
            batch=batch,
            job=job,
            snippets=snippets,
            prompt=prompt,
            continuation_prompt=continuation_prompt,
            rolling_codebook=rolling_codebook,
            client=client,
            workspace_root=workspace_root,
        )

    # Final status
    with Session(engine) as session:
        job = session.exec(select(CodingJob).where(CodingJob.id == job_id)).first()
        batches = session.exec(
            select(CodingBatch).where(CodingBatch.job_id == job_id)
        ).all()
        failed = [b for b in batches if b.status == "failed"]
        done = [b for b in batches if b.status == "done"]

        if failed and done:
            job.status = "partial"
        elif failed and not done:
            job.status = "failed"
        else:
            job.status = "done"

        job.final_codebook_json = {"themes": rolling_codebook}
        job.finished_at = datetime.now(UTC)
        session.add(job)
        session.commit()


def _run_single_batch(
    *,
    engine,
    batch: CodingBatch,
    job: CodingJob,
    snippets: list,
    prompt: str,
    continuation_prompt: str,
    rolling_codebook: list[dict],
    client: LLMClient,
    workspace_root: Path,
) -> None:
    with Session(engine) as session:
        batch = session.exec(select(CodingBatch).where(CodingBatch.id == batch.id)).first()
        batch.status = "running"
        session.add(batch)
        session.commit()

    for attempt in range(MAX_RETRIES + 1):
        try:
            if rolling_codebook:
                codebook_text = json.dumps(rolling_codebook[:30], ensure_ascii=False)
                full_prompt = f"{continuation_prompt}\n\nExisting codebook:\n{codebook_text}"
            else:
                full_prompt = prompt

            context = build_coding_context(
                question=job.question_column,
                responses=batch.input_texts_json,
                knowledge_snippets=snippets,
            )
            raw = client.generate(f"{full_prompt}\n\n{context}")
            parsed = parse_coding_response(raw)

            # Update rolling codebook
            for theme in parsed["themes"]:
                existing_names = {t["theme_name"] for t in rolling_codebook}
                if theme["theme_name"] not in existing_names:
                    rolling_codebook.append(theme)

            with Session(engine) as session:
                batch = session.exec(select(CodingBatch).where(CodingBatch.id == batch.id)).first()
                batch.status = "done"
                batch.output_codes_json = parsed
                session.add(batch)

                job_record = session.exec(select(CodingJob).where(CodingJob.id == job.id)).first()
                job_record.coded_responses += len(batch.input_texts_json)
                session.add(job_record)
                session.commit()
            return

        except Exception as exc:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
                with Session(engine) as session:
                    batch = session.exec(select(CodingBatch).where(CodingBatch.id == batch.id)).first()
                    batch.retry_count = attempt + 1
                    session.add(batch)
                    session.commit()
                continue

            with Session(engine) as session:
                batch = session.exec(select(CodingBatch).where(CodingBatch.id == batch.id)).first()
                batch.status = "failed"
                batch.error_message = str(exc)
                session.add(batch)
                session.commit()
            return


def get_coding_job_status(*, workspace_root: Path, job_id: int) -> dict:
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        job = session.exec(select(CodingJob).where(CodingJob.id == job_id)).first()
        if job is None:
            raise ValueError(f"CodingJob {job_id} not found")
        batches = session.exec(
            select(CodingBatch).where(CodingBatch.job_id == job_id)
        ).all()

    completed = [b for b in batches if b.status == "done"]
    failed = [b for b in batches if b.status == "failed"]

    return {
        "status": job.status,
        "total_batches": len(batches),
        "completed_batches": len(completed),
        "failed_batches": len(failed),
        "coded_responses": job.coded_responses,
        "total_responses": job.total_responses,
    }


def _load_continuation_prompt() -> str:
    prompt_path = (
        Path(__file__).resolve().parent.parent
        / "llm"
        / "prompts"
        / "open_text_coding_continuation.md"
    )
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    # Fallback: use the standard prompt with a codebook preamble
    return load_coding_prompt() + (
        "\n\n## Additional instruction\n"
        "You have an existing codebook from previous batches. "
        "Use the same theme names when applicable. "
        "If you encounter genuinely new themes, add them."
    )
```

Create `src/game_survey_workbench/llm/prompts/open_text_coding_continuation.md`:

```markdown
# Open Text Coding — Continuation Batch

You are coding open-ended survey responses into grounded themes for a game survey research workflow.

## Context

This is a continuation batch. Previous batches have already produced a codebook (provided below). Use the same theme names wherever applicable. If you encounter responses that genuinely do not fit any existing theme, you may add new themes.

## Input

- Question text
- A list of verbatim responses (this batch only)
- Knowledge context from the project knowledge base
- Existing codebook from previous batches

## Task

- Assign each response to an existing theme where possible.
- Only create new themes when a response clearly does not match any existing theme.
- Maintain consistent theme naming with the existing codebook.

## Output

Return JSON with this shape:

```json
{
  "themes": [
    {
      "theme_name": "Theme name",
      "count": 2,
      "example_responses": ["response 1", "response 2"]
    }
  ],
  "uncoded_count": 0
}
```

## Constraints

- Each theme must be grounded in the provided responses.
- `example_responses` should include up to 3 short verbatim examples from this batch.
- If a response does not fit a theme, count it in `uncoded_count`.
- Prefer existing theme names over creating synonyms.
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_batched_coding.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/batched_coding.py src/game_survey_workbench/llm/prompts/open_text_coding_continuation.md tests/test_batched_coding.py
git commit -m "feat(2.0C): add batched coding service with dedup, serial execution, rolling codebook"
```

---

## Task 6: Add coding job routes with progress polling

**Files:**
- Create: `src/game_survey_workbench/routes/coding_jobs.py`
- Modify: `src/game_survey_workbench/app.py`
- Create: `tests/test_coding_job_routes.py`

**Step 1: Write the failing tests**

```python
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.workspace import bootstrap_workspace


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)
    return tmp_path


@pytest.fixture()
def app_client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as c:
        yield c


def test_create_coding_job_returns_job_id(app_client, workspace):
    response = app_client.post(
        "/projects/demo/coding-jobs",
        json={
            "analysis_run_id": "run-1",
            "question_column": "Q1",
            "responses": [f"resp {i}" for i in range(100)],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["total_batches"] >= 1


def test_get_coding_job_status_returns_progress(app_client, workspace):
    create_resp = app_client.post(
        "/projects/demo/coding-jobs",
        json={
            "analysis_run_id": "run-1",
            "question_column": "Q1",
            "responses": ["resp 1", "resp 2"],
        },
    )
    job_id = create_resp.json()["job_id"]

    status_resp = app_client.get(f"/projects/demo/coding-jobs/{job_id}/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert "status" in data
    assert "total_batches" in data
    assert "completed_batches" in data


def test_cancel_coding_job(app_client, workspace):
    create_resp = app_client.post(
        "/projects/demo/coding-jobs",
        json={
            "analysis_run_id": "run-1",
            "question_column": "Q1",
            "responses": ["resp 1"],
        },
    )
    job_id = create_resp.json()["job_id"]

    cancel_resp = app_client.post(f"/projects/demo/coding-jobs/{job_id}/cancel")
    assert cancel_resp.status_code == 200

    status_resp = app_client.get(f"/projects/demo/coding-jobs/{job_id}/status")
    assert status_resp.json()["status"] == "cancelled"
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_coding_job_routes.py -v`

Expected: FAIL — routes do not exist.

**Step 3: Write the minimal implementation**

Create `src/game_survey_workbench/routes/coding_jobs.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.coding_job import CodingJob
from game_survey_workbench.services.batched_coding import (
    create_coding_job,
    get_coding_job_status,
)

router = APIRouter()


class CreateCodingJobRequest(BaseModel):
    analysis_run_id: str
    question_column: str
    responses: list[str]
    batch_size: int = 80


@router.post(
    "/projects/{project_slug}/coding-jobs",
    status_code=status.HTTP_201_CREATED,
)
def create_job(project_slug: str, payload: CreateCodingJobRequest):
    settings = get_settings()
    job, batches = create_coding_job(
        workspace_root=settings.workspace_root,
        project_slug=project_slug,
        analysis_run_id=payload.analysis_run_id,
        question_column=payload.question_column,
        responses=payload.responses,
        batch_size=payload.batch_size,
    )
    return {
        "job_id": job.id,
        "status": job.status,
        "total_batches": len(batches),
        "total_responses": job.total_responses,
    }


@router.get("/projects/{project_slug}/coding-jobs/{job_id}/status")
def job_status(project_slug: str, job_id: int):
    settings = get_settings()
    try:
        return get_coding_job_status(
            workspace_root=settings.workspace_root,
            job_id=job_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_slug}/coding-jobs/{job_id}/cancel")
def cancel_job(project_slug: str, job_id: int):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        job = session.exec(select(CodingJob).where(CodingJob.id == job_id)).first()
        if job is None:
            raise HTTPException(status_code=404, detail="Coding job not found")
        job.status = "cancelled"
        job.finished_at = datetime.now(UTC)
        session.add(job)
        session.commit()
    return {"status": "cancelled"}


@router.post("/projects/{project_slug}/coding-jobs/{job_id}/retry-failed")
def retry_failed_batches(project_slug: str, job_id: int):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        job = session.exec(select(CodingJob).where(CodingJob.id == job_id)).first()
        if job is None:
            raise HTTPException(status_code=404, detail="Coding job not found")
        if job.status not in ("partial", "failed"):
            raise HTTPException(status_code=400, detail="Job has no failed batches to retry")
        # Reset failed batches to pending
        from game_survey_workbench.models.coding_job import CodingBatch
        batches = session.exec(
            select(CodingBatch).where(
                CodingBatch.job_id == job_id,
                CodingBatch.status == "failed",
            )
        ).all()
        for batch in batches:
            batch.status = "pending"
            batch.retry_count = 0
            batch.error_message = None
            session.add(batch)
        job.status = "queued"
        job.finished_at = None
        session.add(job)
        session.commit()
    return {"status": "queued", "retried_batches": len(batches)}
```

Register the router in `src/game_survey_workbench/app.py` by adding:

```python
from game_survey_workbench.routes.coding_jobs import router as coding_jobs_router
app.include_router(coding_jobs_router)
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_coding_job_routes.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/coding_jobs.py src/game_survey_workbench/app.py tests/test_coding_job_routes.py
git commit -m "feat(2.0C): add coding job routes with create, status, cancel, retry"
```

---

## Task 7: Wire batched coding into existing code_open_text_column flow

**Files:**
- Modify: `src/game_survey_workbench/services/text_coding.py`
- Modify: `tests/test_text_coding_service.py`

**Step 1: Write the failing tests**

```python
import json
from pathlib import Path
from unittest.mock import MagicMock

from game_survey_workbench.db import create_db_and_tables
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.workspace import bootstrap_workspace
from game_survey_workbench.services.text_coding import code_open_text_column


def _fake_response():
    return json.dumps({
        "themes": [{"theme_name": "Positive", "count": 5, "example_responses": ["good"]}],
        "uncoded_count": 0,
    })


def test_code_open_text_column_uses_batched_path_for_large_datasets(tmp_path: Path):
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)

    mock_client = MagicMock()
    mock_client.generate.return_value = _fake_response()

    responses = [f"response {i}" for i in range(200)]
    result = code_open_text_column(
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        workspace_root=tmp_path,
        client=mock_client,
    )

    # Should have made multiple LLM calls (batched)
    assert mock_client.generate.call_count > 1
    assert result.themes  # non-empty


def test_code_open_text_column_uses_single_call_for_small_datasets(tmp_path: Path):
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)

    mock_client = MagicMock()
    mock_client.generate.return_value = _fake_response()

    responses = ["response 1", "response 2", "response 3"]
    result = code_open_text_column(
        project_slug="demo",
        analysis_run_id="run-1",
        question_column="Q1",
        responses=responses,
        workspace_root=tmp_path,
        client=mock_client,
    )

    assert mock_client.generate.call_count == 1
    assert result.themes
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_text_coding_service.py::test_code_open_text_column_uses_batched_path_for_large_datasets tests/test_text_coding_service.py::test_code_open_text_column_uses_single_call_for_small_datasets -v`

Expected: FAIL — current implementation always makes exactly 1 LLM call.

**Step 3: Write the minimal implementation**

Modify `code_open_text_column()` in `src/game_survey_workbench/services/text_coding.py`:

```python
from game_survey_workbench.services.batched_coding import (
    DEFAULT_BATCH_SIZE,
    create_coding_job,
    run_coding_job,
    get_coding_job_status,
)


def code_open_text_column(
    *,
    project_slug: str,
    analysis_run_id: str,
    question_column: str,
    responses: list[str],
    workspace_root: Path,
    client: LLMClient,
    top_k: int = 10,
) -> CodingResult:
    clean_responses = [r.strip() for r in responses if r and r.strip()]
    if not clean_responses:
        raise NoFreeTextResponsesFoundError(f"No free-text responses found for '{question_column}'.")

    project = get_project(workspace_root=workspace_root, project_slug=project_slug)
    if project is None:
        raise ProjectNotFoundError("Project not found.")

    if len(clean_responses) <= DEFAULT_BATCH_SIZE:
        return _code_single_batch(
            project_slug=project_slug,
            analysis_run_id=analysis_run_id,
            question_column=question_column,
            responses=clean_responses,
            workspace_root=workspace_root,
            client=client,
            top_k=top_k,
        )

    # Batched path
    job, _batches = create_coding_job(
        workspace_root=workspace_root,
        project_slug=project_slug,
        analysis_run_id=analysis_run_id,
        question_column=question_column,
        responses=clean_responses,
    )
    run_coding_job(
        workspace_root=workspace_root,
        job_id=job.id,
        client=client,
        top_k=top_k,
    )

    status = get_coding_job_status(workspace_root=workspace_root, job_id=job.id)
    codebook = status.get("final_codebook_json") or {}

    # Convert batched result to CodingResult for compatibility
    snippets = retrieve_project_knowledge(
        workspace_root=workspace_root,
        project_slug=project_slug,
        query=question_column,
        stages=["analysis"],
        top_k=top_k,
    )
    result = CodingResult(
        analysis_run_id=analysis_run_id,
        question_column=question_column,
        themes=codebook.get("themes", []),
        uncoded_count=sum(
            b.get("uncoded_count", 0)
            for b in _get_batch_outputs(workspace_root, job.id)
        ),
        citations=snippets,
    )
    return save_coding_result(workspace_root=workspace_root, result=result)
```

Extract the existing single-batch logic into `_code_single_batch()`:

```python
def _code_single_batch(
    *,
    project_slug: str,
    analysis_run_id: str,
    question_column: str,
    responses: list[str],
    workspace_root: Path,
    client: LLMClient,
    top_k: int = 10,
) -> CodingResult:
    """Original single-batch coding path, preserved for small datasets."""
    snippets = retrieve_project_knowledge(
        workspace_root=workspace_root,
        project_slug=project_slug,
        query=question_column,
        stages=["analysis"],
        top_k=top_k,
    )
    if not snippets:
        snippets = retrieve_project_knowledge(
            workspace_root=workspace_root,
            project_slug=project_slug,
            query="",
            stages=["analysis"],
            top_k=top_k,
        )
    context = build_coding_context(
        question=question_column,
        responses=responses,
        knowledge_snippets=snippets,
    )
    prompt = load_coding_prompt()
    raw_output = client.generate(f"{prompt}\n\n{context}")
    parsed = parse_coding_response(raw_output)
    result = CodingResult(
        analysis_run_id=analysis_run_id,
        question_column=question_column,
        themes=parsed["themes"],
        uncoded_count=parsed["uncoded_count"],
        citations=snippets,
    )
    return save_coding_result(workspace_root=workspace_root, result=result)
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_text_coding_service.py -v`

Expected: PASS (both new and existing tests)

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/text_coding.py tests/test_text_coding_service.py
git commit -m "feat(2.0C): wire batched coding into code_open_text_column for large datasets"
```

---

## Task 8: Add codebook merge-review routes and template

**Files:**
- Modify: `src/game_survey_workbench/routes/coding_jobs.py`
- Create: `src/game_survey_workbench/templates/coding_jobs/merge_review.html`
- Create: `tests/test_merge_review.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.coding_job import CodingJob
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.workspace import bootstrap_workspace
from sqlmodel import Session


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    create_project(ProjectCreate(slug="demo", name="Demo"), workspace_root=tmp_path)
    return tmp_path


@pytest.fixture()
def app_client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as c:
        yield c


def _create_done_job(workspace: Path) -> int:
    engine = get_engine(workspace)
    with Session(engine) as session:
        job = CodingJob(
            project_slug="demo",
            analysis_run_id="run-1",
            question_column="Q1",
            status="done",
            total_responses=100,
            coded_responses=100,
            batch_size=80,
            final_codebook_json={
                "themes": [
                    {"theme_name": "Great graphics", "count": 10, "example_responses": ["good visuals"]},
                    {"theme_name": "Good graphics", "count": 8, "example_responses": ["nice art"]},
                    {"theme_name": "Fun gameplay", "count": 15, "example_responses": ["enjoyable"]},
                ]
            },
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job.id


def test_merge_review_shows_codebook(app_client, workspace):
    job_id = _create_done_job(workspace)
    response = app_client.get(f"/projects/demo/coding-jobs/{job_id}/merge-review")
    assert response.status_code == 200
    html = response.text
    assert "Great graphics" in html
    assert "Good graphics" in html
    assert "Fun gameplay" in html


def test_merge_confirm_merges_selected_themes(app_client, workspace):
    job_id = _create_done_job(workspace)
    response = app_client.post(
        f"/projects/demo/coding-jobs/{job_id}/merge-confirm",
        data={
            "merge_group_0_target": "Great graphics",
            "merge_group_0_sources": ["Good graphics"],
        },
        follow_redirects=False,
    )
    assert response.status_code in (200, 303)
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_merge_review.py -v`

Expected: FAIL — merge-review and merge-confirm routes do not exist.

**Step 3: Write the minimal implementation**

Add to `src/game_survey_workbench/routes/coding_jobs.py`:

```python
@router.get("/projects/{project_slug}/coding-jobs/{job_id}/merge-review")
def merge_review(project_slug: str, job_id: int, request: Request):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        job = session.exec(select(CodingJob).where(CodingJob.id == job_id)).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Coding job not found")

    codebook = job.final_codebook_json or {}
    themes = codebook.get("themes", [])

    return templates.TemplateResponse(request, "coding_jobs/merge_review.html", {
        "project_slug": project_slug,
        "job_id": job_id,
        "themes": themes,
    })


@router.post("/projects/{project_slug}/coding-jobs/{job_id}/merge-confirm")
async def merge_confirm(project_slug: str, job_id: int, request: Request):
    settings = get_settings()
    form = await request.form()
    engine = get_engine(settings.workspace_root)

    # Parse merge groups from form
    merge_map: dict[str, str] = {}  # source_name -> target_name
    i = 0
    while f"merge_group_{i}_target" in form:
        target = form.get(f"merge_group_{i}_target")
        sources = form.getlist(f"merge_group_{i}_sources")
        for source in sources:
            if source != target:
                merge_map[source] = target
        i += 1

    with Session(engine) as session:
        job = session.exec(select(CodingJob).where(CodingJob.id == job_id)).first()
        if job is None:
            raise HTTPException(status_code=404, detail="Coding job not found")

        codebook = job.final_codebook_json or {}
        themes = codebook.get("themes", [])

        # Apply merges
        merged_themes: dict[str, dict] = {}
        for theme in themes:
            name = theme["theme_name"]
            target = merge_map.get(name, name)
            if target in merged_themes:
                merged_themes[target]["count"] += theme["count"]
            else:
                merged_themes[target] = {**theme, "theme_name": target}

        job.final_codebook_json = {"themes": list(merged_themes.values())}
        session.add(job)
        session.commit()

    return RedirectResponse(
        url=f"/projects/{project_slug}/analysis/latest",
        status_code=status.HTTP_303_SEE_OTHER,
    )
```

Create template `src/game_survey_workbench/templates/coding_jobs/merge_review.html`:

```html
{% extends "layout.html" %}
{% block content %}
<h2>编码合并审查</h2>
<p>以下是编码主题列表。如有近义主题需要合并，请选择目标名称和要合并的来源。</p>

<form method="post" action="/projects/{{ project_slug }}/coding-jobs/{{ job_id }}/merge-confirm">
  <table>
    <thead>
      <tr>
        <th>主题名</th>
        <th>计数</th>
        <th>示例</th>
      </tr>
    </thead>
    <tbody>
      {% for theme in themes %}
      <tr>
        <td>{{ theme.theme_name }}</td>
        <td>{{ theme.count }}</td>
        <td>{{ theme.example_responses | join(', ') }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <h3>合并设置（可选）</h3>
  <div id="merge-groups">
    <div class="merge-group">
      <label>目标主题名:
        <select name="merge_group_0_target">
          {% for theme in themes %}
          <option value="{{ theme.theme_name }}">{{ theme.theme_name }}</option>
          {% endfor %}
        </select>
      </label>
      <label>合并来源:
        <select name="merge_group_0_sources" multiple>
          {% for theme in themes %}
          <option value="{{ theme.theme_name }}">{{ theme.theme_name }}</option>
          {% endfor %}
        </select>
      </label>
    </div>
  </div>

  <button type="submit">确认合并</button>
  <a href="/projects/{{ project_slug }}/analysis/latest">跳过，直接使用</a>
</form>
{% endblock %}
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_merge_review.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/coding_jobs.py src/game_survey_workbench/templates/coding_jobs/merge_review.html tests/test_merge_review.py
git commit -m "feat(2.0C): add codebook merge-review and merge-confirm flow"
```

---

## Task 9: Add staging file cleanup

**Files:**
- Create: `src/game_survey_workbench/services/staging_cleanup.py`
- Create: `tests/test_staging_cleanup.py`

**Step 1: Write the failing tests**

```python
import time
from pathlib import Path

from game_survey_workbench.services.staging_cleanup import cleanup_stale_staging_files


def test_cleanup_removes_files_older_than_threshold(tmp_path: Path):
    staging_dir = tmp_path / "projects" / "demo" / "data" / "staging"
    staging_dir.mkdir(parents=True)

    old_file = staging_dir / "old.csv"
    old_file.write_text("old data")
    # Backdate modification time by 25 hours
    import os
    old_mtime = time.time() - 90000
    os.utime(old_file, (old_mtime, old_mtime))

    new_file = staging_dir / "new.csv"
    new_file.write_text("new data")

    removed = cleanup_stale_staging_files(workspace_root=tmp_path, max_age_hours=24)
    assert removed == 1
    assert not old_file.exists()
    assert new_file.exists()
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_staging_cleanup.py -v`

Expected: FAIL — module does not exist.

**Step 3: Write the minimal implementation**

```python
from __future__ import annotations

import time
from pathlib import Path


def cleanup_stale_staging_files(*, workspace_root: Path, max_age_hours: int = 24) -> int:
    projects_dir = workspace_root / "projects"
    if not projects_dir.exists():
        return 0

    cutoff = time.time() - (max_age_hours * 3600)
    removed = 0

    for staging_dir in projects_dir.glob("*/data/staging"):
        for f in staging_dir.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1

    return removed
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_staging_cleanup.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/staging_cleanup.py tests/test_staging_cleanup.py
git commit -m "feat(2.0C): add staging file cleanup utility"
```

---

## Task 10: Run full regression and update roadmap

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

Update the "当前执行状态" section in the north-star document to record 2.0C completion status.

**Step 3: Manual verification checklist**

- [ ] Upload a single-header CSV → preview page shows inferred types
- [ ] Upload a dual-header CSV → preview page shows declared types
- [ ] Modify a column type on preview page → confirmed import uses the override
- [ ] Upload a 问卷星-style CSV with `（多选）` header → auto-detected as multi_select
- [ ] Code a question with ≤80 responses → single LLM call, instant result
- [ ] Code a question with 300+ responses → batched, progress visible, result complete
- [ ] Simulate a batch failure → job shows "partial", retry succeeds
- [ ] Cancel a running job → status changes to "cancelled"
- [ ] Merge-review page shows themes → merge two near-duplicates → codebook updated

**Step 4: Commit**

```bash
git add docs/plans/2026-03-15-game-survey-workbench-2.0-north-star.md
git commit -m "docs: update 2.0 roadmap after smart data and batched coding"
```

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Single-header type inference accuracy < 80% | Medium | Medium | Preview page lets users correct; accumulate patterns over time |
| Codebook rolling transfer causes prompt bloat | High | Low | Cap at top-30 themes; compress to `{name, count}` tuples |
| Serial batch execution too slow for 1000+ responses | Medium | Medium | Dedup is the main lever (30-60% reduction); parallel+merge is future option |
| Staging files accumulate on disk | Low | Medium | `cleanup_stale_staging_files()` runs on startup or via scheduled call |
| Batch retry exponential backoff blocks the thread | Low | Low | Max 2 retries with short delays (1s, 2s); total worst-case < 10s per failed batch |

---

## Verification Checklist Before Any Completion Claim

- Run: `.venv/Scripts/python.exe -m pytest tests/test_format_detection.py tests/test_upload_preview.py tests/test_coding_job_model.py tests/test_batched_coding.py tests/test_coding_job_routes.py tests/test_merge_review.py tests/test_staging_cleanup.py -v`
- Run: `.venv/Scripts/python.exe -m pytest -v`
- Run: `.venv/Scripts/python.exe -m compileall src`
- Manually confirm:
  - Single-header and dual-header CSVs both work through the preview flow
  - Small datasets use single-batch coding (1 LLM call)
  - Large datasets use batched coding (multiple LLM calls, progress tracking)
  - Failed batches can be retried
  - Codebook merge-review works
  - Existing 2.0A/2.0B functionality is not broken

## Implementation Phases Summary

| Phase | Tasks | Duration Estimate |
|---|---|---|
| **P1: Smart Data Tolerance** | Tasks 1-3 | 2-3 days |
| **P2: Batched Coding Core** | Tasks 4-7 | 3-4 days |
| **P3: Merge & Polish** | Tasks 8-10 | 2 days |
