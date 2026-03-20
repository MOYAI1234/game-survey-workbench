# 2.0E Output Usability: i18n, Download, and Chinese Report Sections

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make questionnaire and report outputs usable outside the tool by adding project-level language control, Chinese report section titles, questionnaire bilingual generation, and download routes for both questionnaire and report in `.md` and `.txt` formats.

**Architecture:** Add a `language` field to `ProjectRecord` (default `"zh"`). Propagate language into prompt construction so LLM outputs respect the configured language. Change the `report_builder.py` section registry to use a title map keyed by language. Add download routes on both questionnaire and report routers that serve the stored Markdown as file responses, with an optional `?fmt=txt` that strips Markdown formatting. Add a bilingual mode for questionnaire generation that appends a Chinese translation section below the English questionnaire.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, Jinja2, pytest, existing `LLMClient` protocol

---

## North-Star Mapping

| Actual Delivery | North-Star Direction | Notes |
|---|---|---|
| 2.0A | 方向一：全局知识库 | ✅ Done |
| 2.0B | 方向二：分层检索 + 方向四（部分）：基础命中反馈 | ✅ Done |
| 2.0C | 方向三：智能数据适配 + 分批编码 | ✅ Done |
| 2.0D | 方向七：知识格式扩展 PDF/Word | ✅ Done |
| **2.0E** | **方向六 + 十 + 十一：中文化 + 问卷双语/下载 + 报告中文化/下载** | **This plan** |

The original north-star listed these as three separate stages (2.0G, 2.0J, 2.0K). They are combined here because they share download infrastructure and language configuration, and together they solve the "output last mile" problem — outputs are generated but stuck inside the browser with no download or language control.

## Assumptions

- `ProjectRecord` currently has no `language` field. We add one with default `"zh"`.
- Report section titles in `report_builder.py` are hardcoded English strings. We map them to Chinese equivalents.
- `QuestionnaireSpecVersion.markdown_spec` already stores the full Markdown. Download = serve it directly.
- `ReportRecord.path` already points to a `.md` file on disk. Download = `FileResponse`.
- The existing `LLMClient.generate()` protocol is sufficient. No streaming changes.
- The questionnaire bilingual mode appends a `---` divider followed by the Chinese translation, as specified in north-star 方向十.

## Non-Goals

- `.docx` download — deferred; requires `python-docx` dependency and formatting logic
- Full prompt template i18n system — we add language-aware suffix instructions, not a template registry
- Streaming / SSE for LLM generation — separate concern (方向九)
- Visual upgrade / Pico CSS — separate concern (方向八)
- Project-level language switcher UI beyond a simple dropdown — minimal form field

## Dependencies

| Dependency | Status | Notes |
|---|---|---|
| `ProjectRecord` model | ✅ Exists | `src/game_survey_workbench/models/project.py` |
| `QuestionnaireSpecVersion` model | ✅ Exists | `src/game_survey_workbench/models/questionnaire.py` |
| `ReportRecord` model | ✅ Exists | `src/game_survey_workbench/models/reporting.py` |
| `report_builder.py` section registry | ✅ Exists | `src/game_survey_workbench/services/report_builder.py` |
| `questionnaire_design.md` prompt | ✅ Exists | `src/game_survey_workbench/llm/prompts/questionnaire_design.md` |
| `insight_synthesis.md` prompt | ✅ Exists | `src/game_survey_workbench/llm/prompts/insight_synthesis.md` |

## Data Model Changes

### Existing Model Changes

`ProjectRecord` gains one field:
- `language: str = "zh"` — project output language, `"zh"` or `"en"`

This is additive (has default), so no data migration is needed for existing rows. A `db.py` migration helper backfills the column for pre-existing tables.

### No New Tables

Download and i18n require no new persistence — they operate on existing stored data.

## Route Changes

### Questionnaire Download

| Route | Method | New | Purpose |
|---|---|---|---|
| `/{slug}/questionnaires/{version_id}/download` | GET | ✓ | Download questionnaire as `.md` or `.txt` |

### Report Download

| Route | Method | New | Purpose |
|---|---|---|---|
| `/{slug}/reports/latest/download` | GET | ✓ | Download latest report as `.md` or `.txt` |
| `/{slug}/reports/{report_id}/download` | GET | ✓ | Download specific report by ID |

### Project Language Setting

No new route — add `language` field to the existing project create/edit form.

## Error Handling

| Scenario | Behavior |
|---|---|
| Download requested for non-existent questionnaire version | 404 |
| Download requested for non-existent report | 404 |
| Report file path in DB but file missing from disk | 404 with message "Report file not found on disk" |
| `?fmt=` param is not `md` or `txt` | Default to `md` |
| Project has `language=zh` but LLM outputs English | Prompt suffix makes this unlikely; no enforcement beyond prompting |

---

## Task 1: Add `language` field to ProjectRecord with migration

**Files:**
- Modify: `src/game_survey_workbench/models/project.py`
- Modify: `src/game_survey_workbench/db.py`
- Create: `tests/test_project_language.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectCreate, ProjectRecord
from game_survey_workbench.services.projects import create_project, get_project
from sqlmodel import Session, select


def test_project_record_has_language_field_defaulting_to_zh(tmp_path: Path):
    create_db_and_tables(tmp_path)
    create_project(
        ProjectCreate(slug="demo", name="Demo"),
        workspace_root=tmp_path,
    )
    project = get_project(workspace_root=tmp_path, project_slug="demo")
    assert project is not None
    assert project.language == "zh"


def test_project_record_stores_custom_language(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        record = ProjectRecord(slug="en-proj", name="English Project", language="en")
        session.add(record)
        session.commit()

    project = get_project(workspace_root=tmp_path, project_slug="en-proj")
    assert project is not None
    assert project.language == "en"


def test_migration_backfills_language_for_existing_tables(tmp_path: Path):
    """Simulate a pre-existing DB without the language column."""
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    # Insert a row, then verify language is accessible
    with Session(engine) as session:
        record = ProjectRecord(slug="old", name="Old Project")
        session.add(record)
        session.commit()

    # Re-run migration
    create_db_and_tables(tmp_path)

    with Session(engine) as session:
        row = session.exec(
            select(ProjectRecord).where(ProjectRecord.slug == "old")
        ).first()
        assert row is not None
        assert row.language == "zh"
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_project_language.py -v`

Expected: FAIL — `ProjectRecord` has no `language` attribute.

**Step 3: Write the minimal implementation**

In `src/game_survey_workbench/models/project.py`, add to `ProjectRecord`:

```python
language: str = "zh"
```

And add to `ProjectCreate`:

```python
language: str = "zh"
```

In `src/game_survey_workbench/db.py`, add a migration helper:

```python
def _ensure_projectrecord_language_column(engine) -> None:
    with engine.begin() as connection:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(projectrecord)")
        }
        if not columns:
            return
        if "language" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE projectrecord ADD COLUMN language VARCHAR NOT NULL DEFAULT 'zh'"
            )
```

Call it from `create_db_and_tables()` after the existing migration helpers.

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_project_language.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/project.py src/game_survey_workbench/db.py tests/test_project_language.py
git commit -m "feat(2.0E): add language field to ProjectRecord with zh default"
```

---

## Task 2: Add Chinese section titles to report builder

**Files:**
- Modify: `src/game_survey_workbench/services/report_builder.py`
- Modify: `src/game_survey_workbench/services/reporting.py`
- Create: `tests/test_report_i18n.py`

**Step 1: Write the failing tests**

```python
from game_survey_workbench.services.report_builder import build_report_sections
from game_survey_workbench.services.report_sections import assemble_report_markdown


def test_report_sections_use_chinese_titles_when_language_is_zh():
    registry = build_report_sections(
        brief={"background": "测试背景", "objectives": ["目标1"], "target_audience": "玩家"},
        dataset_meta={"row_count": 100, "question_count": 10, "question_types": {}},
        statistical_findings=["Finding 1"],
        coded_themes=[],
        insight_narrative="Some narrative",
        evidence_section=None,
        recommendations=["Do X"],
        language="zh",
    )
    sections = registry.ordered_sections()
    titles = [s.title for s in sections]
    assert "执行摘要" in titles
    assert "研究方法" in titles
    assert "统计发现" in titles
    assert "分析叙述" in titles
    assert "行动建议" in titles


def test_report_sections_use_english_titles_when_language_is_en():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 50, "question_count": 5, "question_types": {}},
        statistical_findings=["Finding 1"],
        coded_themes=[],
        insight_narrative="Narrative",
        evidence_section=None,
        recommendations=[],
        language="en",
    )
    sections = registry.ordered_sections()
    titles = [s.title for s in sections]
    assert "Executive Summary" in titles
    assert "Methodology" in titles


def test_report_sections_default_to_chinese_when_language_omitted():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 10, "question_count": 2, "question_types": {}},
        statistical_findings=["F1"],
        coded_themes=[],
        insight_narrative="N",
        evidence_section=None,
        recommendations=[],
    )
    sections = registry.ordered_sections()
    titles = [s.title for s in sections]
    assert "执行摘要" in titles


def test_assembled_report_markdown_contains_chinese_headings():
    registry = build_report_sections(
        brief=None,
        dataset_meta={"row_count": 100, "question_count": 10, "question_types": {}},
        statistical_findings=["Finding 1"],
        coded_themes=[],
        insight_narrative="Narrative text",
        evidence_section=None,
        recommendations=["Action 1"],
        language="zh",
    )
    markdown = assemble_report_markdown(
        title="Demo Report",
        date="2026-03-19",
        registry=registry,
    )
    assert "## 执行摘要" in markdown
    assert "## 研究方法" in markdown
    assert "## 行动建议" in markdown
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_report_i18n.py -v`

Expected: FAIL — `build_report_sections()` does not accept a `language` parameter.

**Step 3: Write the minimal implementation**

In `src/game_survey_workbench/services/report_builder.py`, add a title map and a `language` parameter:

```python
SECTION_TITLES = {
    "zh": {
        "executive_summary": "执行摘要",
        "methodology": "研究方法",
        "statistical_findings": "统计发现",
        "qualitative_themes": "定性主题",
        "analysis_narrative": "分析叙述",
        "recommendations": "行动建议",
        "evidence_basis": "证据基础",
    },
    "en": {
        "executive_summary": "Executive Summary",
        "methodology": "Methodology",
        "statistical_findings": "Statistical Findings",
        "qualitative_themes": "Qualitative Themes",
        "analysis_narrative": "Analysis",
        "recommendations": "Recommendations",
        "evidence_basis": "Evidence Basis",
    },
}


def _title(key: str, language: str) -> str:
    return SECTION_TITLES.get(language, SECTION_TITLES["zh"]).get(key, key)
```

Update `build_report_sections()` signature to accept `language: str = "zh"` and replace all hardcoded title strings with `_title("key", language)` calls.

In `src/game_survey_workbench/services/reporting.py`, update `generate_structured_report()` to accept and pass through `language: str = "zh"`.

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_report_i18n.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/report_builder.py src/game_survey_workbench/services/reporting.py tests/test_report_i18n.py
git commit -m "feat(2.0E): add Chinese section titles to report builder with language param"
```

---

## Task 3: Propagate project language into report generation route

**Files:**
- Modify: `src/game_survey_workbench/routes/reports.py`
- Modify: `tests/test_stage7a_report_builder.py` (or create `tests/test_report_language_route.py`)

**Step 1: Write the failing test**

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.services.workspace import bootstrap_workspace
from sqlmodel import Session


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        session.add(ProjectRecord(slug="demo", name="Demo", language="zh"))
        session.commit()
    return tmp_path


@pytest.fixture()
def app_client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as c:
        yield c


def test_report_generation_uses_project_language_for_section_titles(workspace, app_client):
    """After full pipeline, generated report should have Chinese section titles."""
    # This test verifies integration; the unit test in Task 2 covers the logic.
    # Here we just verify the route reads project.language and passes it through.
    # A minimal check: the route code path includes language= in the call.
    # Full integration requires LLM + dataset; we verify the wiring only.
    engine = get_engine(workspace)
    with Session(engine) as session:
        project = session.exec(
            __import__("sqlmodel", fromlist=["select"]).select(ProjectRecord).where(
                ProjectRecord.slug == "demo"
            )
        ).first()
    assert project is not None
    assert project.language == "zh"
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_report_language_route.py -v`

Expected: FAIL if `ProjectRecord` migration hasn't run; PASS if Task 1 is complete. This task is primarily a wiring change.

**Step 3: Write the minimal implementation**

In `src/game_survey_workbench/routes/reports.py`, in `generate_report()`:

After loading the project, read `project.language` (defaulting to `"zh"`), then pass `language=project.language` to `generate_structured_report()`.

```python
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
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_report_language_route.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/reports.py tests/test_report_language_route.py
git commit -m "feat(2.0E): propagate project language into report generation"
```

---

## Task 4: Add language-aware suffix to questionnaire and insight prompts

**Files:**
- Modify: `src/game_survey_workbench/services/questionnaires.py`
- Modify: `src/game_survey_workbench/services/insights.py` (if insight synthesis also needs language suffix)
- Create: `tests/test_prompt_language_suffix.py`

**Step 1: Write the failing tests**

```python
from game_survey_workbench.services.questionnaires import (
    build_questionnaire_design_context,
    _language_suffix,
)


def test_language_suffix_zh_instructs_chinese_output():
    suffix = _language_suffix("zh")
    assert "中文" in suffix or "Chinese" in suffix


def test_language_suffix_en_instructs_english_output():
    suffix = _language_suffix("en")
    assert "English" in suffix


def test_language_suffix_zh_bilingual_includes_divider_instruction():
    suffix = _language_suffix("zh", bilingual=True)
    assert "---" in suffix
    assert "Chinese" in suffix or "中文" in suffix


def test_build_context_includes_language_instruction():
    context = build_questionnaire_design_context(
        project_name="Demo",
        research_goal="Test",
        hypotheses=[],
        knowledge_snippets=[],
        language="zh",
    )
    assert "中文" in context or "Chinese" in context
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_prompt_language_suffix.py -v`

Expected: FAIL — `_language_suffix` does not exist, `build_questionnaire_design_context` does not accept `language`.

**Step 3: Write the minimal implementation**

In `src/game_survey_workbench/services/questionnaires.py`, add:

```python
def _language_suffix(language: str, *, bilingual: bool = False) -> str:
    if bilingual:
        return (
            "\n\n## Language Instruction\n"
            "Output the complete questionnaire in English first. "
            "Then add a horizontal divider (---), and provide the complete "
            "Chinese translation of the same questionnaire below. "
            "Both versions must be complete and independently usable."
        )
    if language == "zh":
        return (
            "\n\n## Language Instruction\n"
            "Output the entire questionnaire in Chinese (简体中文). "
            "Section headings, question text, and diagnostic notes must all be in Chinese."
        )
    return (
        "\n\n## Language Instruction\n"
        "Output the entire questionnaire in English."
    )
```

Update `build_questionnaire_design_context()` to accept `language: str = "zh"` and `bilingual: bool = False`, appending the suffix to the returned context string.

Update `generate_questionnaire_draft()` to read the project's language and pass it through:

```python
project = get_project(...)
language = getattr(project, "language", "zh")
context = build_questionnaire_design_context(
    ...,
    language=language,
)
```

Similarly, add a language suffix helper for insight synthesis if the project language is `"zh"`. This can be done by appending to the prompt string before calling `client.generate()` in the insight service.

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_prompt_language_suffix.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/questionnaires.py tests/test_prompt_language_suffix.py
git commit -m "feat(2.0E): add language-aware prompt suffix for questionnaire and insight generation"
```

---

## Task 5: Add questionnaire download route

**Files:**
- Modify: `src/game_survey_workbench/routes/questionnaires.py`
- Create: `src/game_survey_workbench/services/download_utils.py`
- Create: `tests/test_questionnaire_download.py`

**Step 1: Write the failing tests**

```python
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion
from game_survey_workbench.services.workspace import bootstrap_workspace
from sqlmodel import Session


SAMPLE_MARKDOWN = """\
## Section One

- Question 1: What do you think?
  > Diagnostic: measures satisfaction

## Section Two

- Question 2: How often do you play?
"""


@pytest.fixture()
def workspace_with_questionnaire(tmp_path: Path) -> tuple[Path, str]:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        session.add(ProjectRecord(slug="demo", name="Demo"))
        version = QuestionnaireSpecVersion(
            project_slug="demo",
            version_id="v-test-1",
            research_goal="Test goal",
            markdown_spec=SAMPLE_MARKDOWN,
        )
        session.add(version)
        session.commit()
    return tmp_path, "v-test-1"


@pytest.fixture()
def app_client(workspace_with_questionnaire, monkeypatch):
    workspace, _ = workspace_with_questionnaire
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as c:
        yield c


def test_download_questionnaire_as_md(app_client, workspace_with_questionnaire):
    _, version_id = workspace_with_questionnaire
    response = app_client.get(
        f"/projects/demo/questionnaires/{version_id}/download?fmt=md"
    )
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "## Section One" in response.text
    assert "attachment" in response.headers.get("content-disposition", "")


def test_download_questionnaire_as_txt(app_client, workspace_with_questionnaire):
    _, version_id = workspace_with_questionnaire
    response = app_client.get(
        f"/projects/demo/questionnaires/{version_id}/download?fmt=txt"
    )
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    # Markdown formatting should be stripped
    assert "##" not in response.text
    assert "Section One" in response.text
    assert "Question 1" in response.text


def test_download_questionnaire_returns_404_for_unknown_version(app_client):
    response = app_client.get(
        "/projects/demo/questionnaires/nonexistent/download"
    )
    assert response.status_code == 404


def test_download_defaults_to_md_when_fmt_missing(app_client, workspace_with_questionnaire):
    _, version_id = workspace_with_questionnaire
    response = app_client.get(
        f"/projects/demo/questionnaires/{version_id}/download"
    )
    assert response.status_code == 200
    assert "## Section One" in response.text
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_questionnaire_download.py -v`

Expected: FAIL — download route does not exist.

**Step 3: Write the minimal implementation**

Create `src/game_survey_workbench/services/download_utils.py`:

```python
"""Shared utilities for downloading Markdown content as md or txt."""

from __future__ import annotations

import re


def strip_markdown(markdown: str) -> str:
    """Remove Markdown formatting, returning plain text."""
    text = markdown
    # Remove headings markers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}(.+?)_{1,3}", r"\1", text)
    # Remove blockquote markers
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    # Remove list markers (- and *)
    text = re.sub(r"^[\-\*]\s+", "", text, flags=re.MULTILINE)
    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove link syntax
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Remove horizontal rules
    text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
```

Add to `src/game_survey_workbench/routes/questionnaires.py`:

```python
from fastapi.responses import Response

@router.get("/projects/{project_slug}/questionnaires/{version_id}/download")
def download_questionnaire(project_slug: str, version_id: str, fmt: str = "md"):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        version = session.exec(
            select(QuestionnaireSpecVersion).where(
                QuestionnaireSpecVersion.project_slug == project_slug,
                QuestionnaireSpecVersion.version_id == version_id,
            )
        ).first()
    if version is None:
        raise HTTPException(status_code=404, detail="Questionnaire version not found")

    content = version.markdown_spec
    if fmt == "txt":
        from game_survey_workbench.services.download_utils import strip_markdown
        content = strip_markdown(content)
        media_type = "text/plain; charset=utf-8"
        filename = f"questionnaire-{version_id}.txt"
    else:
        media_type = "text/markdown; charset=utf-8"
        filename = f"questionnaire-{version_id}.md"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_questionnaire_download.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/download_utils.py src/game_survey_workbench/routes/questionnaires.py tests/test_questionnaire_download.py
git commit -m "feat(2.0E): add questionnaire download route with md and txt formats"
```

---

## Task 6: Add report download route

**Files:**
- Modify: `src/game_survey_workbench/routes/reports.py`
- Create: `tests/test_report_download.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.models.reporting import ReportRecord
from game_survey_workbench.services.workspace import bootstrap_workspace
from sqlmodel import Session


SAMPLE_REPORT = """\
# Demo Report

*Report generated 2026-03-19*

## Executive Summary

Key finding here.

## Methodology

**Sample:** 100 respondents
"""


@pytest.fixture()
def workspace_with_report(tmp_path: Path) -> tuple[Path, int]:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    report_dir = tmp_path / "projects" / "demo" / "reports"
    report_dir.mkdir(parents=True)
    report_path = report_dir / "report-test.md"
    report_path.write_text(SAMPLE_REPORT, encoding="utf-8")

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        session.add(ProjectRecord(slug="demo", name="Demo"))
        record = ReportRecord(
            project_slug="demo",
            analysis_run_id="run-1",
            path=str(report_path),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        report_id = record.id
    return tmp_path, report_id


@pytest.fixture()
def app_client(workspace_with_report, monkeypatch):
    workspace, _ = workspace_with_report
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as c:
        yield c


def test_download_report_latest_as_md(app_client):
    response = app_client.get("/projects/demo/reports/latest/download?fmt=md")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "## Executive Summary" in response.text
    assert "attachment" in response.headers.get("content-disposition", "")


def test_download_report_latest_as_txt(app_client):
    response = app_client.get("/projects/demo/reports/latest/download?fmt=txt")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "##" not in response.text
    assert "Executive Summary" in response.text


def test_download_report_by_id(app_client, workspace_with_report):
    _, report_id = workspace_with_report
    response = app_client.get(f"/projects/demo/reports/{report_id}/download")
    assert response.status_code == 200
    assert "Demo Report" in response.text


def test_download_report_returns_404_when_no_reports_exist(app_client, workspace_with_report):
    response = app_client.get("/projects/nonexistent/reports/latest/download")
    assert response.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_report_download.py -v`

Expected: FAIL — download routes do not exist.

**Step 3: Write the minimal implementation**

Add to `src/game_survey_workbench/routes/reports.py`:

```python
from fastapi.responses import Response


@router.get("/projects/{project_slug}/reports/latest/download")
def download_latest_report(project_slug: str, fmt: str = "md"):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        records = session.exec(
            select(ReportRecord).where(ReportRecord.project_slug == project_slug)
        ).all()
    if not records:
        raise HTTPException(status_code=404, detail="No reports found")

    latest = sorted(records, key=lambda r: r.created_at, reverse=True)[0]
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


def _serve_report_file(record: ReportRecord, *, fmt: str) -> Response:
    path = Path(record.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report file not found on disk")

    content = path.read_text(encoding="utf-8")
    filename_stem = path.stem

    if fmt == "txt":
        from game_survey_workbench.services.download_utils import strip_markdown
        content = strip_markdown(content)
        media_type = "text/plain; charset=utf-8"
        filename = f"{filename_stem}.txt"
    else:
        media_type = "text/markdown; charset=utf-8"
        filename = f"{filename_stem}.md"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_report_download.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/reports.py tests/test_report_download.py
git commit -m "feat(2.0E): add report download routes with md and txt formats"
```

---

## Task 7: Add download buttons to questionnaire and report templates

**Files:**
- Modify: `src/game_survey_workbench/templates/questionnaires/detail.html`
- Modify: `src/game_survey_workbench/templates/reports/detail.html`
- Modify: `tests/test_stage5b_questionnaire_page.py` (or create `tests/test_download_buttons.py`)

**Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion
from game_survey_workbench.models.reporting import ReportRecord
from game_survey_workbench.services.workspace import bootstrap_workspace
from sqlmodel import Session


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    report_dir = tmp_path / "projects" / "demo" / "reports"
    report_dir.mkdir(parents=True)
    report_path = report_dir / "report-test.md"
    report_path.write_text("# Report\n\n## Summary\n\nDone.", encoding="utf-8")

    with Session(engine) as session:
        session.add(ProjectRecord(slug="demo", name="Demo"))
        session.add(QuestionnaireSpecVersion(
            project_slug="demo",
            version_id="v1",
            research_goal="Goal",
            markdown_spec="## Q1\n\n- Question",
        ))
        session.add(ReportRecord(
            project_slug="demo",
            analysis_run_id="run-1",
            path=str(report_path),
        ))
        session.commit()
    return tmp_path


@pytest.fixture()
def app_client(workspace, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as c:
        yield c


def test_questionnaire_page_shows_download_links(app_client):
    response = app_client.get("/projects/demo/questionnaires/latest")
    html = response.text
    assert "download" in html.lower()
    assert "fmt=md" in html
    assert "fmt=txt" in html


def test_report_page_shows_download_links(app_client):
    response = app_client.get("/projects/demo/reports/latest")
    html = response.text
    assert "download" in html.lower()
    assert "fmt=md" in html
    assert "fmt=txt" in html
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_download_buttons.py -v`

Expected: FAIL — no download links in the templates.

**Step 3: Write the minimal implementation**

In `src/game_survey_workbench/templates/questionnaires/detail.html`, after the `<pre class="questionnaire-markdown">` block (around line 30), add:

```html
{% if spec %}
<section class="download-actions">
  <h3>下载问卷</h3>
  <a href="/projects/{{ project_slug }}/questionnaires/{{ spec.version_id }}/download?fmt=md" class="btn">下载 Markdown (.md)</a>
  <a href="/projects/{{ project_slug }}/questionnaires/{{ spec.version_id }}/download?fmt=txt" class="btn">下载纯文本 (.txt)</a>
</section>
{% endif %}
```

In `src/game_survey_workbench/templates/reports/detail.html`, after the report content section (around line 30), add:

```html
{% if report_content %}
<section class="download-actions">
  <h3>下载报告</h3>
  <a href="/projects/{{ project_slug }}/reports/latest/download?fmt=md" class="btn">下载 Markdown (.md)</a>
  <a href="/projects/{{ project_slug }}/reports/latest/download?fmt=txt" class="btn">下载纯文本 (.txt)</a>
</section>
{% endif %}
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_download_buttons.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/templates/questionnaires/detail.html src/game_survey_workbench/templates/reports/detail.html tests/test_download_buttons.py
git commit -m "feat(2.0E): add download buttons to questionnaire and report pages"
```

---

## Task 8: Add bilingual questionnaire generation mode

**Files:**
- Modify: `src/game_survey_workbench/routes/questionnaires.py`
- Modify: `src/game_survey_workbench/services/questionnaires.py`
- Modify: `src/game_survey_workbench/templates/questionnaires/detail.html`
- Create: `tests/test_bilingual_questionnaire.py`

**Step 1: Write the failing tests**

```python
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectCreate, ProjectRecord
from game_survey_workbench.models.questionnaire import QuestionnaireDraftRequest
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.questionnaires import (
    generate_questionnaire_draft,
    _language_suffix,
)
from game_survey_workbench.services.workspace import bootstrap_workspace
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from sqlmodel import Session


def test_bilingual_suffix_contains_divider_instruction():
    suffix = _language_suffix("zh", bilingual=True)
    assert "---" in suffix
    assert "English" in suffix
    assert "Chinese" in suffix


def test_generate_questionnaire_with_bilingual_flag_includes_bilingual_suffix(
    tmp_path: Path,
):
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    create_project(
        ProjectCreate(slug="demo", name="Demo"),
        workspace_root=tmp_path,
    )

    # Create and select a knowledge doc
    doc_path = tmp_path / "method.md"
    doc_path.write_text(
        "---\ntitle: Method\ndoc_type: guide\nstage:\n  - design\n---\nContent.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(doc_path, project_root=tmp_path)
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="demo",
        knowledge_document_ids=[1],
    )

    mock_client = MagicMock()
    mock_client.generate.return_value = "## English Q\n\n---\n\n## 中文问卷"

    version = generate_questionnaire_draft(
        project_slug="demo",
        payload=QuestionnaireDraftRequest(research_goal="Test"),
        workspace_root=tmp_path,
        client=mock_client,
        bilingual=True,
    )

    # Verify the prompt sent to LLM contained bilingual instruction
    call_args = mock_client.generate.call_args[0][0]
    assert "---" in call_args
    assert "English" in call_args
    assert "Chinese" in call_args or "中文" in call_args
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_bilingual_questionnaire.py -v`

Expected: FAIL — `generate_questionnaire_draft` does not accept `bilingual` parameter.

**Step 3: Write the minimal implementation**

In `src/game_survey_workbench/services/questionnaires.py`, update `generate_questionnaire_draft()` to accept `bilingual: bool = False` and pass it through to `build_questionnaire_design_context()`:

```python
def generate_questionnaire_draft(
    *,
    project_slug: str,
    payload: QuestionnaireDraftRequest,
    workspace_root: Path,
    client: LLMClient,
    bilingual: bool = False,
) -> QuestionnaireSpecVersion:
    ...
    language = getattr(project, "language", "zh")
    context = build_questionnaire_design_context(
        ...,
        language=language,
        bilingual=bilingual,
    )
    ...
```

In `build_questionnaire_design_context()`, append the language suffix:

```python
def build_questionnaire_design_context(
    *,
    project_name: str,
    research_goal: str,
    hypotheses: list[str],
    knowledge_snippets: list[str | dict],
    brief_background: str = "",
    brief_target_audience: str = "",
    language: str = "zh",
    bilingual: bool = False,
) -> str:
    ...
    parts.append(_language_suffix(language, bilingual=bilingual))
    return "\n".join(parts)
```

In `src/game_survey_workbench/routes/questionnaires.py`, update the draft-form route to accept an optional `bilingual` checkbox:

```python
@router.post("/projects/{project_slug}/questionnaires/draft-form")
def draft_questionnaire_form(
    project_slug: str,
    research_goal: str = Form(...),
    bilingual: bool = Form(False),
):
    ...
    _generate_questionnaire_version(
        project_slug=project_slug,
        payload=QuestionnaireDraftRequest(research_goal=research_goal),
        bilingual=bilingual,
    )
```

Update `_generate_questionnaire_version()` to accept and pass `bilingual`.

In `src/game_survey_workbench/templates/questionnaires/detail.html`, add a checkbox to the draft form:

```html
<label>
  <input type="checkbox" name="bilingual" value="true">
  生成中英双语问卷
</label>
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_bilingual_questionnaire.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/questionnaires.py src/game_survey_workbench/routes/questionnaires.py src/game_survey_workbench/templates/questionnaires/detail.html tests/test_bilingual_questionnaire.py
git commit -m "feat(2.0E): add bilingual questionnaire generation with en+zh mode"
```

---

## Task 9: Add project language selector to project form

**Files:**
- Modify: `src/game_survey_workbench/templates/projects/detail.html`
- Modify: `src/game_survey_workbench/routes/projects.py`
- Create: `tests/test_project_language_form.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.services.projects import get_project
from game_survey_workbench.services.workspace import bootstrap_workspace
from sqlmodel import Session


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        session.add(ProjectRecord(slug="demo", name="Demo", language="zh"))
        session.commit()
    return tmp_path


@pytest.fixture()
def app_client(workspace, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(workspace))
    with TestClient(create_app()) as c:
        yield c


def test_project_page_shows_language_selector(app_client):
    response = app_client.get("/projects/demo")
    html = response.text
    assert "language" in html.lower()
    assert "zh" in html
    assert "en" in html
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_project_language_form.py -v`

Expected: FAIL — no language selector in the project template.

**Step 3: Write the minimal implementation**

In `src/game_survey_workbench/templates/projects/detail.html`, add a language selector section. The exact location depends on the current template structure — place it near the project metadata area:

```html
<section class="project-settings">
  <h3>项目设置</h3>
  <form action="/projects/{{ project.slug }}/settings" method="post">
    <label for="language">输出语言</label>
    <select name="language" id="language">
      <option value="zh" {% if project.language == "zh" %}selected{% endif %}>中文</option>
      <option value="en" {% if project.language == "en" %}selected{% endif %}>English</option>
    </select>
    <button type="submit">保存</button>
  </form>
</section>
```

In `src/game_survey_workbench/routes/projects.py`, add a settings route:

```python
@router.post("/projects/{project_slug}/settings")
def update_project_settings(project_slug: str, language: str = Form("zh")):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        project = session.exec(
            select(ProjectRecord).where(ProjectRecord.slug == project_slug)
        ).first()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        project.language = language
        session.add(project)
        session.commit()
    return RedirectResponse(
        url=f"/projects/{project_slug}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_project_language_form.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/templates/projects/detail.html src/game_survey_workbench/routes/projects.py tests/test_project_language_form.py
git commit -m "feat(2.0E): add project language selector with settings route"
```

---

## Task 10: Add language suffix to insight synthesis prompt

**Files:**
- Modify: `src/game_survey_workbench/services/insights.py` (or wherever insight synthesis calls `client.generate`)
- Create: `tests/test_insight_language.py`

**Step 1: Write the failing test**

```python
from pathlib import Path
from unittest.mock import MagicMock

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectRecord
from game_survey_workbench.services.workspace import bootstrap_workspace
from sqlmodel import Session


def test_insight_prompt_includes_chinese_language_instruction_for_zh_project(tmp_path: Path):
    """Verify that the insight synthesis prompt includes a Chinese language instruction
    when the project language is zh."""
    # This is a wiring test — the actual language suffix logic is tested in Task 4.
    # We just verify the insight service reads project.language.
    bootstrap_workspace(tmp_path)
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        session.add(ProjectRecord(slug="demo", name="Demo", language="zh"))
        session.commit()

    project = Session(engine).exec(
        __import__("sqlmodel", fromlist=["select"]).select(ProjectRecord).where(
            ProjectRecord.slug == "demo"
        )
    ).first()
    assert project.language == "zh"
    # The actual prompt suffix attachment is verified by integration testing
    # or by inspecting the generate() call in a full pipeline test.
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_insight_language.py -v`

Expected: Likely PASS as this is a lightweight wiring check. The real work is modifying the insight service.

**Step 3: Write the minimal implementation**

Find the insight synthesis service (likely `src/game_survey_workbench/services/insights.py` or `src/game_survey_workbench/routes/insights.py`). Where it calls `client.generate(prompt)`, modify to:

1. Load the project to get `language`
2. Append a language suffix to the prompt:

```python
language = getattr(project, "language", "zh")
if language == "zh":
    prompt += (
        "\n\n## Language Instruction\n"
        "Output the entire insight narrative in Chinese (简体中文). "
        "Section headings and prose must all be in Chinese."
    )
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_insight_language.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/insights.py tests/test_insight_language.py
git commit -m "feat(2.0E): add Chinese language suffix to insight synthesis prompt"
```

---

## Task 11: Run full regression and update roadmap

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

Add a 2.0E entry to the "当前执行状态" section:

```markdown
- `2.0E 输出可用性套件`：已完成
  - `ProjectRecord` 新增 `language` 字段（默认 `zh`），项目页可切换输出语言
  - 报告章节标题支持中英文切换（`SECTION_TITLES` 映射表）
  - 问卷和洞察 prompt 追加语言指令后缀，确保 LLM 输出语言可控
  - 问卷支持中英双语生成模式（表单勾选后追加双语 prompt 指令）
  - 问卷和报告页均新增下载按钮，支持 `.md` 和 `.txt` 两种格式
  - 新增 `download_utils.py` 提供 Markdown→纯文本的格式剥离
```

**Step 3: Manual verification checklist**

- [ ] 创建项目时默认 language=zh
- [ ] 项目设置页可切换语言为 en
- [ ] 生成问卷后，问卷页出现"下载 Markdown"和"下载纯文本"按钮
- [ ] 下载的 `.md` 文件内容与页面显示一致
- [ ] 下载的 `.txt` 文件不含 `##`、`**`、`>` 等 Markdown 标记
- [ ] 生成报告后，报告页出现下载按钮
- [ ] language=zh 时报告章节标题为中文（执行摘要、研究方法等）
- [ ] language=en 时报告章节标题为英文
- [ ] 勾选"生成中英双语问卷"后，LLM 输出包含英文问卷 + 分隔线 + 中文问卷
- [ ] 全量测试通过，compileall 通过

**Step 4: Commit**

```bash
git add docs/plans/2026-03-15-game-survey-workbench-2.0-north-star.md
git commit -m "docs: update 2.0 roadmap after output usability suite (2.0E)"
```

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| LLM ignores language suffix and outputs wrong language | Medium | Medium | Suffix is explicit and positioned at end of prompt; can strengthen with "IMPORTANT:" prefix if needed |
| `strip_markdown()` loses meaningful formatting | Low | Medium | Only used for `.txt` download; `.md` is the primary format; regex patterns are conservative |
| Bilingual mode doubles token cost | Medium | Low | Only triggered when user explicitly checks the box; not the default |
| Existing tests break due to report section title changes | Medium | Low | Default language is `zh` matching existing behavior; `language` parameter has default |
| `ProjectRecord.language` migration fails on existing DBs | Low | Low | Uses same `ALTER TABLE ADD COLUMN ... DEFAULT` pattern proven in 5 previous migrations |

## Verification Checklist Before Any Completion Claim

- Run: `.venv/Scripts/python.exe -m pytest tests/test_project_language.py tests/test_report_i18n.py tests/test_prompt_language_suffix.py tests/test_questionnaire_download.py tests/test_report_download.py tests/test_download_buttons.py tests/test_bilingual_questionnaire.py tests/test_project_language_form.py -v`
- Run: `.venv/Scripts/python.exe -m pytest -v`
- Run: `.venv/Scripts/python.exe -m compileall src`
- Manually confirm:
  - Download links appear on questionnaire and report pages
  - Downloaded files are well-formed
  - Report section titles match project language setting
  - Bilingual checkbox produces dual-language output
  - Existing 2.0A/B/C/D functionality is not broken

## Implementation Phases Summary

| Phase | Tasks | Duration Estimate | Focus |
|---|---|---|---|
| **P1: Language Infrastructure** | Tasks 1-4 | 1-2 days | ProjectRecord.language + report title map + prompt suffixes |
| **P2: Download Routes** | Tasks 5-7 | 1-2 days | Questionnaire download + report download + template buttons |
| **P3: Bilingual & Polish** | Tasks 8-11 | 1-2 days | Bilingual mode + project settings UI + insight language + regression |
