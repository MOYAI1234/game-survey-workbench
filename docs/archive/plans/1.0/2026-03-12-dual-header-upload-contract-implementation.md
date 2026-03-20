# Dual Header Upload Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace heuristic-first survey import with a strict dual-header upload contract that requires the second header row to define question types explicitly.

**Architecture:** Keep the current FastAPI + pandas import pipeline, but change parsing so dataset import reads the first two rows as a contract. The first row becomes the displayed column title, the second row becomes the normalized type source of truth, and malformed uploads are rejected with explicit `400` errors instead of falling back to heuristics.

**Tech Stack:** Python 3.12, FastAPI, pandas, openpyxl, SQLModel, pytest, httpx/TestClient, uv.

---

### Task 1: Add dual-header parsing primitives

**Files:**
- Create: `src/game_survey_workbench/services/upload_contract.py`
- Create: `tests/test_upload_contract.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from game_survey_workbench.services.upload_contract import parse_dual_header_dataframe


def test_parse_dual_header_dataframe_extracts_titles_types_and_rows(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "分层,Q1,Q2\n"
        "metadata,single_choice,free_text\n"
        "免费玩家,满意,希望奖励更多\n",
        encoding="utf-8",
    )

    parsed = parse_dual_header_dataframe(csv_path)

    assert parsed.column_titles == ["分层", "Q1", "Q2"]
    assert parsed.column_types == ["metadata", "single_choice", "free_text"]
    assert parsed.dataframe.iloc[0].to_dict() == {
        "分层": "免费玩家",
        "Q1": "满意",
        "Q2": "希望奖励更多",
    }
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_upload_contract.py -v`
Expected: FAIL because the upload contract service does not exist.

**Step 3: Write minimal implementation**

```python
ALLOWED_TYPE_MARKERS = {
    "metadata",
    "single_choice",
    "multi_select",
    "free_text",
    "scale",
}


class ParsedDualHeaderDataset(SQLModel):
    column_titles: list[str]
    column_types: list[str]
    dataframe: pd.DataFrame
```

Implement a parser that:

- loads CSV or Excel without assuming a single header row
- reads row 1 as titles
- reads row 2 as type markers
- reads row 3+ as data rows
- assigns row-1 titles as the final DataFrame column names

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_upload_contract.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/upload_contract.py tests/test_upload_contract.py
git commit -m "feat: add dual-header upload parsing primitives"
```

### Task 2: Enforce strict dual-header validation

**Files:**
- Modify: `src/game_survey_workbench/services/upload_contract.py`
- Modify: `tests/test_upload_contract.py`

**Step 1: Write the failing tests**

```python
import pytest

from game_survey_workbench.services.upload_contract import parse_dual_header_dataframe


def test_parse_dual_header_dataframe_rejects_missing_type_row(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text("Q1,Q2\n满意,建议更多奖励\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Missing type marker row"):
        parse_dual_header_dataframe(csv_path)


def test_parse_dual_header_dataframe_rejects_unknown_type_marker(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "Q1,Q2\nsingle_choice,matrix\n满意,高\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsupported type marker 'matrix'"):
        parse_dual_header_dataframe(csv_path)
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_upload_contract.py -v`
Expected: FAIL because validation is not strict enough.

**Step 3: Write minimal implementation**

Validate that:

- the file has at least two rows
- every type marker cell is present and non-blank
- every type marker is in the allowed set
- duplicate blank or malformed titles are rejected if discovered

Raise `ValueError` with actionable messages that mention row/column context when practical.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_upload_contract.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/upload_contract.py tests/test_upload_contract.py
git commit -m "feat: validate dual-header upload contract"
```

### Task 3: Refactor dataset import to use declared types

**Files:**
- Modify: `src/game_survey_workbench/services/dataset_import.py`
- Modify: `tests/test_dataset_import.py`

**Step 1: Write the failing tests**

```python
def test_import_dataset_uses_second_header_row_as_type_source_of_truth(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "分层,Q1,Q2\n"
        "metadata,multi_select,free_text\n"
        "免费玩家,Reward A;Reward B,希望奖励更多\n",
        encoding="utf-8",
    )

    dataset = import_dataset(csv_path, project_slug="demo", workspace_root=tmp_path)

    assert "分层" not in dataset.question_columns
    assert dataset.question_columns["Q1"].question_type == "multi_select"
    assert dataset.question_columns["Q2"].question_type == "free_text"
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_dataset_import.py -v`
Expected: FAIL because import still depends on one-row headers and heuristics.

**Step 3: Write minimal implementation**

Update import flow to:

- call the dual-header parser
- use row-1 labels as schema keys
- use row-2 markers to assign `question_type`
- exclude `metadata` from `question_columns`
- keep `QuestionColumnSchema` persistence behavior unchanged

Keep heuristic helpers only if needed for future compatibility, but they should no longer drive this import path.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_dataset_import.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/dataset_import.py tests/test_dataset_import.py
git commit -m "feat: use declared types for dataset import"
```

### Task 4: Reject malformed uploads at the HTTP boundary

**Files:**
- Modify: `src/game_survey_workbench/routes/datasets.py`
- Modify: `tests/test_dataset_import.py`

**Step 1: Write the failing tests**

```python
def test_import_dataset_route_rejects_upload_without_type_row(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    client = TestClient(create_app())
    client.post("/projects", json={"slug": "upload-demo", "name": "Upload Demo", "knowledge_pack": {}})

    response = client.post(
        "/projects/upload-demo/datasets/import",
        files={"file": ("survey.csv", "Q1,Q2\n满意,建议更多奖励\n", "text/csv")},
    )

    assert response.status_code == 400
    assert "Missing type marker row" in response.json()["detail"]
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_dataset_import.py -v`
Expected: FAIL because `ValueError` is not translated into an HTTP `400`.

**Step 3: Write minimal implementation**

Catch contract-validation errors in the dataset import route and return:

- `400 Bad Request`
- `detail` message containing the parser error text

Do not add heuristic fallback.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_dataset_import.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/datasets.py tests/test_dataset_import.py
git commit -m "fix: reject malformed survey uploads with clear errors"
```

### Task 5: Convert real-sample fixtures to the dual-header contract

**Files:**
- Modify: `tests/fixtures/surveys/basic_survey.csv`
- Create: `tests/fixtures/surveys/bb_stress_sample.csv`
- Modify: `tests/test_real_sample_understanding.py`
- Modify: `tests/test_end_to_end_smoke.py`

**Step 1: Write the failing tests**

```python
def test_bb_real_sample_treats_segment_column_as_metadata(tmp_path: Path):
    dataset = import_dataset(BB_FIXTURE, project_slug="bb", workspace_root=tmp_path)

    assert "分层" not in dataset.question_columns


def test_wc_real_sample_uses_declared_types_from_second_header_row(tmp_path: Path):
    dataset = import_dataset(WC_FIXTURE, project_slug="wc", workspace_root=tmp_path)

    assert dataset.question_columns["What are your most satisfying parts of Season Pass?"].question_type == "multi_select"
    assert dataset.question_columns["Feel free to tell us what rewards you want to see in the Season Pass!"].question_type == "free_text"
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_real_sample_understanding.py tests/test_end_to_end_smoke.py -v`
Expected: FAIL until fixtures and import path are aligned with the new format.

**Step 3: Write minimal implementation**

- convert the WC fixture to two header rows
- add a redacted BB fixture with `分层` marked as `metadata`
- update smoke data to follow the same contract
- keep fixture data as small as possible while still representing real structure

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_real_sample_understanding.py tests/test_end_to_end_smoke.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/fixtures/surveys/basic_survey.csv tests/fixtures/surveys/bb_stress_sample.csv tests/test_real_sample_understanding.py tests/test_end_to_end_smoke.py
git commit -m "test: cover dual-header contract with real survey fixtures"
```

### Task 6: Publish the upload template and contract docs

**Files:**
- Create: `docs/templates/survey_import_template.csv`
- Modify: `README.md`
- Modify: `scripts/verify_local_http.py`

**Step 1: Write the failing tests**

Add or extend tests to assert the smoke path still works with the new template-backed format:

```python
def test_end_to_end_flow_creates_report(client, seeded_workspace):
    ...
    assert report["analysis_run_id"] == dataset["analysis_run_id"]
```

If the existing smoke test already covers this, do not add redundant assertions; instead rely on the failing smoke test from Task 5 as the red step for this task.

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_end_to_end_smoke.py -v`
Expected: FAIL until docs/example files and local verification script are aligned with the new contract.

**Step 3: Write minimal implementation**

- add a template CSV that demonstrates two header rows
- update README to document:
  - required two-row header structure
  - allowed type markers
  - malformed uploads are rejected
- update `scripts/verify_local_http.py` to keep posting a compliant file and to print contract-relevant verification signals

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_end_to_end_smoke.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add docs/templates/survey_import_template.csv README.md scripts/verify_local_http.py
git commit -m "docs: publish dual-header upload contract"
```

## Verification Checklist Before Any Implementation Claim

- Run: `python -m uv run pytest -v`
- Run: `python -m uv run python -m compileall src`
- Run: `python -m uv run --with uvicorn --with httpx python scripts/verify_local_http.py`
- Manually confirm:
  - compliant dual-header CSV upload succeeds
  - compliant dual-header Excel upload succeeds
  - malformed uploads return `400` with actionable error messages
  - `metadata` columns such as `分层` do not appear in `question_columns`
  - declared `multi_select` and `free_text` types persist into normalized schema
  - report generation still succeeds through persisted `analysis_run_id`

## Risks and Notes

- This is an intentional breaking change for legacy one-header uploads. Do not add silent fallback.
- Keep type markers ASCII and lowercase in docs and templates to reduce ambiguity.
- Avoid reintroducing heuristic-first behavior during route-level error handling.
- If Excel header parsing reveals merged cells or export quirks, reject clearly in this iteration rather than adding partial support.
