# Game Survey Workbench Data Quality Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve the reliability of survey data understanding so real uploads produce trustworthy schemas and analysis inputs.

**Architecture:** Keep the current Python monolith, but refactor dataset import into explicit stages: file persistence, column profiling, column classification, question type detection, schema persistence, and analysis run creation. Reports will consume persisted analysis-run records instead of loose IDs.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, pandas, pytest, httpx/TestClient, uv.

---

### Task 1: Add column classification primitives

**Files:**
- Modify: `src/game_survey_workbench/models/dataset.py`
- Create: `src/game_survey_workbench/services/dataset_schema.py`
- Create: `tests/test_dataset_schema.py`

**Step 1: Write the failing test**

```python
from game_survey_workbench.services.dataset_schema import classify_column


def test_classify_column_marks_timestamp_as_metadata():
    result = classify_column("时间戳记")

    assert result == "metadata"
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_dataset_schema.py -v`
Expected: FAIL because the schema service does not exist.

**Step 3: Write minimal implementation**

```python
METADATA_NAMES = {"标记", "时间戳记"}


def classify_column(column_name: str) -> str:
    if column_name in METADATA_NAMES:
        return "metadata"
    return "question"
```

Extend the result shape so later tasks can store:

- `column_role`
- `include_in_analysis`
- `reason`

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_dataset_schema.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/dataset.py src/game_survey_workbench/services/dataset_schema.py tests/test_dataset_schema.py
git commit -m "feat: add dataset column classification primitives"
```

### Task 2: Improve question type detection for real survey patterns

**Files:**
- Modify: `src/game_survey_workbench/services/dataset_import.py`
- Modify: `src/game_survey_workbench/services/dataset_schema.py`
- Modify: `tests/test_dataset_import.py`

**Step 1: Write the failing tests**

```python
def test_detect_question_type_marks_multiple_choices_question_as_multi_select():
    result = detect_question_type_from_header_and_series(
        "What are your most satisfying parts? (Multiple Choices)",
        pd.Series(["Reward A;Reward B", "Reward C"]),
    )

    assert result == "multi_select"


def test_detect_question_type_marks_free_text_prompt_as_free_text():
    result = detect_question_type_from_header_and_series(
        "Feel free to tell us your suggestion",
        pd.Series(["More rewards please", "It feels expensive"]),
    )

    assert result == "free_text"
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_dataset_import.py -v`
Expected: FAIL because only simple single-choice/scale detection exists.

**Step 3: Write minimal implementation**

```python
def detect_question_type_from_header_and_series(header: str, series: pd.Series) -> str:
    lowered = header.lower()
    if "multiple choices" in lowered:
        return "multi_select"
    if "feel free" in lowered or "suggestion" in lowered:
        return "free_text"
    return detect_question_type(series)
```

Then refine with:

- text-length heuristics for free text
- separator heuristics for multi-select
- numeric-density heuristics for scale

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_dataset_import.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/dataset_import.py src/game_survey_workbench/services/dataset_schema.py tests/test_dataset_import.py
git commit -m "feat: improve question type detection heuristics"
```

### Task 3: Exclude metadata columns from analysis schema

**Files:**
- Modify: `src/game_survey_workbench/services/dataset_import.py`
- Modify: `tests/test_dataset_import.py`

**Step 1: Write the failing test**

```python
def test_import_dataset_excludes_metadata_columns_from_question_schema(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "标记,时间戳记,Q1\n1,2026-03-12 10:00,满意\n",
        encoding="utf-8",
    )

    dataset = import_dataset(csv_path, project_slug="demo", workspace_root=tmp_path)

    assert "标记" not in dataset.question_columns
    assert "时间戳记" not in dataset.question_columns
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_dataset_import.py -v`
Expected: FAIL because metadata columns are still included.

**Step 3: Write minimal implementation**

```python
if classify_column(column) == "metadata":
    continue
```

Persist metadata information separately if useful, but keep it out of analysis-facing question schema.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_dataset_import.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/services/dataset_import.py tests/test_dataset_import.py
git commit -m "feat: exclude metadata columns from analysis schema"
```

### Task 4: Persist richer normalized dataset schema

**Files:**
- Modify: `src/game_survey_workbench/models/dataset.py`
- Modify: `src/game_survey_workbench/services/dataset_import.py`
- Create: `tests/test_dataset_schema_persistence.py`

**Step 1: Write the failing test**

```python
def test_import_dataset_persists_column_role_and_analysis_flags(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text("Q1,Q1_其他说明\n满意,节奏太慢\n", encoding="utf-8")

    dataset = import_dataset(csv_path, project_slug="demo", workspace_root=tmp_path)

    assert dataset.question_columns["Q1"].column_role == "question"
    assert dataset.question_columns["Q1"].include_in_analysis is True
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_dataset_schema_persistence.py -v`
Expected: FAIL because the schema model does not store richer metadata.

**Step 3: Write minimal implementation**

```python
class QuestionColumnSchema(SQLModel):
    column_role: str = "question"
    question_type: str
    include_in_analysis: bool = True
    other_text_column: str | None = None
    reason: str | None = None
```

Update JSON persistence so saved schema files include these fields.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_dataset_schema_persistence.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/dataset.py src/game_survey_workbench/services/dataset_import.py tests/test_dataset_schema_persistence.py
git commit -m "feat: persist richer normalized dataset schema"
```

### Task 5: Introduce a real Analysis Run model

**Files:**
- Create: `src/game_survey_workbench/models/analysis_run.py`
- Modify: `src/game_survey_workbench/db.py`
- Modify: `src/game_survey_workbench/services/dataset_import.py`
- Create: `tests/test_analysis_run.py`

**Step 1: Write the failing test**

```python
def test_import_dataset_creates_analysis_run_record(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text("Q1,Q2\n满意,5\n", encoding="utf-8")

    dataset = import_dataset(csv_path, project_slug="demo", workspace_root=tmp_path)

    run = get_analysis_run(dataset.analysis_run_id, workspace_root=tmp_path)

    assert run.project_slug == "demo"
    assert run.dataset_id == dataset.dataset_id
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_analysis_run.py -v`
Expected: FAIL because no analysis-run model/service exists.

**Step 3: Write minimal implementation**

```python
class AnalysisRunRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    analysis_run_id: str = Field(index=True, unique=True)
    project_slug: str = Field(index=True)
    dataset_id: str = Field(index=True)
    status: str = "ready"
```

Create a small retrieval helper used by report generation.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_analysis_run.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/models/analysis_run.py src/game_survey_workbench/db.py src/game_survey_workbench/services/dataset_import.py tests/test_analysis_run.py
git commit -m "feat: add persisted analysis run records"
```

### Task 6: Tighten report generation to consume persisted analysis runs

**Files:**
- Modify: `src/game_survey_workbench/routes/reports.py`
- Modify: `src/game_survey_workbench/services/reporting.py`
- Modify: `tests/test_reporting.py`

**Step 1: Write the failing test**

```python
def test_generate_report_uses_analysis_run_record_for_project_validation(...):
    ...
```

Use a scenario where:

- dataset belongs to project A
- report request is sent to project B

The request should fail.

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_reporting.py -v`
Expected: FAIL because validation is still too thin.

**Step 3: Write minimal implementation**

Replace loose dataset lookup logic with analysis-run lookup logic.

The route should:

- load `AnalysisRunRecord`
- ensure it exists
- ensure `project_slug` matches route project

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_reporting.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/game_survey_workbench/routes/reports.py src/game_survey_workbench/services/reporting.py tests/test_reporting.py
git commit -m "fix: tie report generation to persisted analysis runs"
```

### Task 7: Add a real-sample regression fixture for survey understanding

**Files:**
- Create: `tests/fixtures/surveys/wc_pass_sample.csv`
- Create: `tests/test_real_sample_understanding.py`

**Step 1: Write the failing test**

```python
def test_real_sample_fixture_marks_multiple_choice_and_free_text_correctly(...):
    dataset = import_dataset(FIXTURE, project_slug="real-check", workspace_root=tmp_path)

    assert dataset.question_columns["What are your most satisfying parts of Season Pass? (Multiple Choices)"].question_type == "multi_select"
    assert dataset.question_columns["Feel free to tell us what rewards you want to see in the Season Pass! You could also give us more suggestion about the game here!"].question_type == "free_text"
```

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_real_sample_understanding.py -v`
Expected: FAIL until the fixture and heuristics align.

**Step 3: Write minimal implementation**

Create a redacted fixture modeled after the real acceptance sample.

Adjust heuristics only as much as needed to satisfy the fixture without overfitting.

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_real_sample_understanding.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/fixtures/surveys/wc_pass_sample.csv tests/test_real_sample_understanding.py
git commit -m "test: add real sample regression coverage for survey understanding"
```

### Task 8: Verify the upgraded import-to-report pipeline end to end

**Files:**
- Modify: `tests/test_end_to_end_smoke.py`
- Modify: `README.md`

**Step 1: Write the failing test**

Extend the smoke test to assert:

- metadata columns are absent from `question_columns`
- uploaded files still work
- generated report still succeeds through the persisted `Analysis Run`

**Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_end_to_end_smoke.py -v`
Expected: FAIL until the upgraded assertions match behavior.

**Step 3: Write minimal implementation**

Update fixtures or helper code only as needed.

Also update README to explain:

- upload API expects multipart file upload
- current recognized question types

**Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_end_to_end_smoke.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_end_to_end_smoke.py README.md
git commit -m "test: verify improved survey understanding end to end"
```

## Verification Checklist Before Any Implementation Claim

- Run: `python -m uv run pytest -v`
- Run: `python -m uv run python -m compileall src`
- Start the app locally and confirm:
  - real CSV/Excel upload still succeeds
  - metadata columns do not appear in `question_columns`
  - multi-select and free-text questions are recognized in the normalized schema
  - a valid analysis run can still generate a Markdown report

## Risks and Notes

- Do not overfit heuristics to only one survey file; use header keywords plus value-shape signals together.
- Keep metadata filtering explicit and test-backed so future rules do not reintroduce system columns.
- Avoid coupling report logic back to raw file parsing; it should rely on persisted analysis-run data.
- If matrix detection starts expanding the scope too much, keep a placeholder type and defer deep matrix normalization to the following iteration.
