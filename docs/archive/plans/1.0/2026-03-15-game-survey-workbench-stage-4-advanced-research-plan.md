# Stage 4: Advanced Research Capability Expansion — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand the workbench from basic descriptive summaries to investigative-grade analysis — cross-tabulation, matrix/ranking question support, stronger LLM-driven recommendations, and a knowledge feedback loop that turns report findings into reusable project knowledge.

**Architecture:** Extend the existing analytics service with cross-tabulation and new question-type summarizers. Add `matrix` and `ranking` to the upload contract and dataset schema pipeline. Strengthen the insight-synthesis prompt to produce structured recommendations. Add a report-to-knowledge feedback route that persists key findings back into the knowledge store as experience-layer entries. All changes stay within the existing FastAPI + SQLModel + Jinja2 stack.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, pandas, pytest, httpx/TestClient (all existing). No new dependencies.

**North-star alignment:** This plan implements the Stage 4 scope from the north-star document — "richer question-type support, matrix and ranking normalization improvements, stronger cross-analysis workflows, richer recommendation logic, deeper knowledge feedback loops from reports and prior projects." It does not change the core product loop or the local-first delivery model.

**Prerequisite state:** Stage 3 completed, 113 tests passing on local master. All prior stage outputs (projects, briefs, plans, questionnaire drafts, coding results, insight records, reports) are functional end-to-end.

## Execution Status

As of 2026-03-15, this Stage 4 plan has been executed on `master`.

- Task 1 `Cross-tabulation analytics engine`: completed
- Task 2 `Matrix question type support`: completed
- Task 3 `Ranking question type support`: completed
- Task 4 `Enhanced recommendation logic in insight synthesis`: completed
- Task 5 `Report-to-knowledge feedback loop`: completed
- Task 6 `North-star update + regression verification`: completed

Implementation notes:

- `/insights` now forwards Stage 4 evidence types into the synthesis prompt, including cross-tab, matrix, and ranking findings.
- `POST /crosstabs` is available for live analysis-run segmentation.
- `POST /reports/feedback-to-knowledge` persists report findings as experience-layer Markdown.
- Final regression verification after Stage 4 execution reached `138 passed`.

Execution commits on `master`:

- `1c1e4a4` `feat(stage4a): add cross-tabulation analytics engine with route and auto-findings`
- `439b2bc` `feat(stage4b): add matrix question analytics and findings`
- `ea92d9e` `feat(stage4c): add ranking question type with normalization and deterministic findings`
- `cacf386` `feat(stage4d): add recommendation context builder and strengthen insight synthesis prompt`
- `5cd0df9` `feat(stage4e): add report-to-knowledge feedback loop for experience-layer persistence`
- `4f83882` `docs: update north-star with Stage 4 sub-stage breakdown and status tracking`

---

## Priority assessment: Stage 4 vs. deferred polish

### Stage 2/3 deferred polish items (NOT addressed here)

| Item | Why it stays deferred |
|------|----------------------|
| Generic report executive summary line | Cosmetic — the provider-backed Key Findings section is already credible |
| Scripted harness prompt alignment | Test infra, not product value |
| Form-based UI for brief/plan editing | UX convenience, not core loop |
| LLM-powered brief generation | Nice-to-have, manual brief entry works |
| CSS/styling polish | Shell, not substance |

**Rationale:** These items do not block the core research loop. Stage 4 analytics directly increase the product's usefulness for real survey projects. Shipping cross-tabs and matrix support before polishing the executive summary line is the correct priority order per the north-star rule: "Prefer work that strengthens the core loop over shell polish."

---

## Scope summary

| Sub-stage | What it delivers | Priority |
|-----------|-----------------|----------|
| 4A | Cross-tabulation analytics engine | Highest — unlocks segmented analysis |
| 4B | Matrix question type support | High — most common unhandled survey type |
| 4C | Ranking question type support | Medium — less common but needed for completeness |
| 4D | Enhanced recommendation logic in insight synthesis | Medium — improves LLM output quality |
| 4E | Report-to-knowledge feedback loop | Medium — closes the knowledge cycle |
| 4F | North-star update + regression verification | Required — bookkeeping |

Each sub-stage is independently shippable and testable.

---

## Non-goals for Stage 4

- Statistical significance testing (chi-square, t-test) — future candidate
- Visualization / charting — product is Markdown-first
- Multi-dataset comparison across projects — future candidate
- Automated cohort discovery — future candidate
- Embedding-based semantic retrieval upgrade — future candidate
- External data connectors — out of north-star scope
- Multi-user / collaboration features — explicitly excluded by north-star

---

## Task 1: Cross-tabulation analytics engine (Stage 4A)

**Files:**
- Create: `src/game_survey_workbench/services/crosstab.py`
- Create: `src/game_survey_workbench/models/crosstab.py`
- Modify: `src/game_survey_workbench/services/analysis_context.py`
- Create: `src/game_survey_workbench/routes/crosstabs.py`
- Modify: `src/game_survey_workbench/app.py`
- Create: `tests/test_crosstab.py`

### Step 1: Write the failing test

```python
# tests/test_crosstab.py
import pandas as pd
import pytest

from game_survey_workbench.services.crosstab import (
    compute_crosstab,
    describe_crosstab,
)
from game_survey_workbench.models.crosstab import CrosstabResult


def test_crosstab_single_choice_by_single_choice():
    df = pd.DataFrame({
        "Q1_Satisfaction": ["Very Satisfied", "Dissatisfied", "Very Satisfied", "Neutral", "Dissatisfied"],
        "Q2_PlayerType": ["Whale", "Minnow", "Whale", "Minnow", "Whale"],
    })
    result = compute_crosstab(
        dataframe=df,
        row_column="Q1_Satisfaction",
        col_column="Q2_PlayerType",
    )
    assert isinstance(result, CrosstabResult)
    assert result.row_column == "Q1_Satisfaction"
    assert result.col_column == "Q2_PlayerType"
    assert "Whale" in result.col_values
    assert "Minnow" in result.col_values
    # Whale: 2 Very Satisfied, 1 Dissatisfied
    whale_dist = result.table["Whale"]
    assert whale_dist["Very Satisfied"]["count"] == 2
    assert whale_dist["Dissatisfied"]["count"] == 1
    # Percentages should sum to ~1.0 per column
    whale_pct_sum = sum(v["percentage"] for v in whale_dist.values())
    assert abs(whale_pct_sum - 1.0) < 0.01


def test_crosstab_scale_by_single_choice():
    df = pd.DataFrame({
        "Q1_Score": [5, 2, 4, 3, 1],
        "Q2_Region": ["NA", "EU", "NA", "EU", "NA"],
    })
    result = compute_crosstab(
        dataframe=df,
        row_column="Q1_Score",
        col_column="Q2_Region",
        row_type="scale",
    )
    # Scale crosstab should give per-group mean and top-box
    assert "NA" in result.col_values
    na_summary = result.group_summaries["NA"]
    assert "mean" in na_summary
    assert "top_box_rate" in na_summary
    # NA scores: 5, 4, 1 -> mean ~3.333
    assert abs(na_summary["mean"] - 3.333) < 0.01


def test_describe_crosstab_returns_readable_text():
    df = pd.DataFrame({
        "Satisfaction": ["High", "Low", "High", "High"],
        "Segment": ["Payer", "Free", "Payer", "Free"],
    })
    result = compute_crosstab(dataframe=df, row_column="Satisfaction", col_column="Segment")
    text = describe_crosstab(result)
    assert "Satisfaction" in text
    assert "Segment" in text
    assert "Payer" in text


def test_crosstab_empty_column_raises():
    df = pd.DataFrame({"A": pd.Series(dtype=str), "B": pd.Series(dtype=str)})
    with pytest.raises(ValueError, match="empty"):
        compute_crosstab(dataframe=df, row_column="A", col_column="B")
```

### Step 2: Run test to verify it fails

Run: `.venv/Scripts/python.exe -m pytest tests/test_crosstab.py -v`
Expected: FAIL — modules do not exist.

### Step 3: Implement model

```python
# src/game_survey_workbench/models/crosstab.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CrosstabResult:
    row_column: str
    col_column: str
    row_values: list[str]
    col_values: list[str]
    # table[col_value][row_value] = {"count": int, "percentage": float}
    table: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)
    # group_summaries[col_value] = {"mean": float, "top_box_rate": float} (scale only)
    group_summaries: dict[str, dict[str, float]] = field(default_factory=dict)
```

### Step 4: Implement service

```python
# src/game_survey_workbench/services/crosstab.py
from __future__ import annotations

import pandas as pd

from game_survey_workbench.models.crosstab import CrosstabResult


def compute_crosstab(
    *,
    dataframe: pd.DataFrame,
    row_column: str,
    col_column: str,
    row_type: str = "categorical",
    top_box_values: set[int] | None = None,
) -> CrosstabResult:
    if top_box_values is None:
        top_box_values = {4, 5}

    working = dataframe[[row_column, col_column]].dropna()
    if working.empty:
        raise ValueError(f"Cross-tab input is empty after dropping nulls from '{row_column}' x '{col_column}'.")

    col_values = sorted(working[col_column].astype(str).unique().tolist())
    row_values = sorted(working[row_column].astype(str).unique().tolist())

    table: dict[str, dict[str, dict[str, float]]] = {}
    group_summaries: dict[str, dict[str, float]] = {}

    for col_val in col_values:
        mask = working[col_column].astype(str) == col_val
        subset = working.loc[mask, row_column]
        total = len(subset)

        if row_type == "scale":
            numeric = pd.to_numeric(subset, errors="coerce").dropna()
            group_summaries[col_val] = {
                "mean": round(float(numeric.mean()), 3) if not numeric.empty else 0.0,
                "top_box_rate": round(
                    float(numeric.isin(top_box_values).mean()), 3
                ) if not numeric.empty else 0.0,
                "n": int(total),
            }
        else:
            dist: dict[str, dict[str, float]] = {}
            counts = subset.astype(str).value_counts()
            for row_val in row_values:
                count = int(counts.get(row_val, 0))
                dist[row_val] = {
                    "count": count,
                    "percentage": round(count / total, 3) if total else 0.0,
                }
            table[col_val] = dist

    return CrosstabResult(
        row_column=row_column,
        col_column=col_column,
        row_values=row_values,
        col_values=col_values,
        table=table,
        group_summaries=group_summaries,
    )


def describe_crosstab(result: CrosstabResult) -> str:
    lines = [f"Cross-tabulation: {result.row_column} by {result.col_column}"]
    if result.group_summaries:
        for col_val, summary in result.group_summaries.items():
            lines.append(
                f"  {col_val}: mean {summary.get('mean', 0):.3f}, "
                f"top-box {summary.get('top_box_rate', 0) * 100:.1f}%, "
                f"n={summary.get('n', 0)}"
            )
    elif result.table:
        for col_val, dist in result.table.items():
            top_row = max(dist.items(), key=lambda x: x[1]["count"])
            lines.append(
                f"  {col_val}: top '{top_row[0]}' "
                f"({int(top_row[1]['count'])} responses, {top_row[1]['percentage'] * 100:.1f}%)"
            )
    return "\n".join(lines)
```

### Step 5: Add route

```python
# src/game_survey_workbench/routes/crosstabs.py
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from game_survey_workbench.config import get_settings
from game_survey_workbench.services.analysis_context import load_analysis_run_context
from game_survey_workbench.services.crosstab import compute_crosstab, describe_crosstab

router = APIRouter()


class CrosstabRequest(BaseModel):
    analysis_run_id: str
    row_column: str
    col_column: str
    row_type: str = "categorical"


@router.post("/crosstabs")
def create_crosstab(payload: CrosstabRequest):
    settings = get_settings()
    context = load_analysis_run_context(
        analysis_run_id=payload.analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    result = compute_crosstab(
        dataframe=context.dataframe,
        row_column=payload.row_column,
        col_column=payload.col_column,
        row_type=payload.row_type,
    )
    return {
        "row_column": result.row_column,
        "col_column": result.col_column,
        "table": result.table,
        "group_summaries": result.group_summaries,
        "description": describe_crosstab(result),
    }
```

Register router in `app.py`:
```python
from game_survey_workbench.routes.crosstabs import router as crosstabs_router
app.include_router(crosstabs_router)
```

### Step 6: Extend deterministic findings with cross-tab support

In `services/analysis_context.py`, add a helper that auto-generates cross-tab descriptions for scale questions segmented by single-choice columns:

```python
def build_crosstab_findings_for_run(
    *,
    analysis_run_id: str,
    workspace_root: Path,
    segment_column: str,
) -> list[str]:
    context = load_analysis_run_context(
        analysis_run_id=analysis_run_id,
        workspace_root=workspace_root,
    )
    findings: list[str] = []
    for question_column, question_payload in context.dataset_record.dataset_schema.items():
        if not isinstance(question_payload, dict):
            continue
        schema = QuestionColumnSchema.model_validate(question_payload)
        if not schema.include_in_analysis or question_column not in context.dataframe.columns:
            continue
        if schema.question_type not in ("scale", "single_choice"):
            continue
        if question_column == segment_column:
            continue

        from game_survey_workbench.services.crosstab import compute_crosstab, describe_crosstab
        try:
            result = compute_crosstab(
                dataframe=context.dataframe,
                row_column=question_column,
                col_column=segment_column,
                row_type=schema.question_type,
            )
            findings.append(describe_crosstab(result))
        except ValueError:
            continue

    return findings
```

### Step 7: Run test to verify it passes

Run: `.venv/Scripts/python.exe -m pytest tests/test_crosstab.py -v`
Expected: 4 passed

### Step 8: Run full regression

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 113+ passed, 0 failed

### Step 9: Commit

```bash
git add src/game_survey_workbench/models/crosstab.py src/game_survey_workbench/services/crosstab.py src/game_survey_workbench/routes/crosstabs.py src/game_survey_workbench/services/analysis_context.py src/game_survey_workbench/app.py tests/test_crosstab.py
git commit -m "feat(stage4a): add cross-tabulation analytics engine with route and auto-findings"
```

---

## Task 2: Matrix question type support (Stage 4B)

**Files:**
- Modify: `src/game_survey_workbench/services/upload_contract.py`
- Modify: `src/game_survey_workbench/models/dataset.py`
- Create: `src/game_survey_workbench/services/matrix_analytics.py`
- Modify: `src/game_survey_workbench/services/analytics.py`
- Modify: `src/game_survey_workbench/services/analysis_context.py`
- Create: `tests/test_matrix_questions.py`

### Step 1: Write the failing test

```python
# tests/test_matrix_questions.py
from pathlib import Path

import pandas as pd
import pytest

from game_survey_workbench.services.matrix_analytics import (
    detect_matrix_group,
    summarize_matrix_group,
    describe_matrix_summary,
)


def test_detect_matrix_group_by_prefix():
    columns = [
        "Q5_画面表现",
        "Q5_音效表现",
        "Q5_操作手感",
        "Q6_整体满意度",
    ]
    groups = detect_matrix_group(columns, prefix="Q5_")
    assert len(groups) == 3
    assert "Q5_画面表现" in groups
    assert "Q5_音效表现" in groups
    assert "Q5_操作手感" in groups


def test_summarize_matrix_group():
    df = pd.DataFrame({
        "Q5_Graphics": [5, 4, 3, 5, 4],
        "Q5_Sound": [3, 2, 4, 3, 2],
        "Q5_Controls": [5, 5, 5, 4, 5],
    })
    matrix_cols = ["Q5_Graphics", "Q5_Sound", "Q5_Controls"]
    summary = summarize_matrix_group(
        dataframe=df,
        columns=matrix_cols,
        top_box_values={4, 5},
    )
    assert len(summary) == 3
    # Controls should have highest mean (all 4-5)
    controls = summary["Q5_Controls"]
    assert controls["mean"] >= 4.5
    assert controls["top_box_rate"] == 1.0
    # Sound should have lowest mean
    sound = summary["Q5_Sound"]
    assert sound["mean"] < controls["mean"]


def test_describe_matrix_summary():
    df = pd.DataFrame({
        "Q5_A": [5, 4, 5],
        "Q5_B": [2, 3, 2],
    })
    summary = summarize_matrix_group(
        dataframe=df, columns=["Q5_A", "Q5_B"], top_box_values={4, 5}
    )
    text = describe_matrix_summary("Q5 Satisfaction Battery", summary)
    assert "Q5_A" in text
    assert "Q5_B" in text
    assert "mean" in text.lower() or "Mean" in text


def test_matrix_type_in_upload_contract():
    from game_survey_workbench.services.upload_contract import ALLOWED_TYPE_MARKERS
    assert "matrix" in ALLOWED_TYPE_MARKERS
```

### Step 2: Run test to verify it fails

Run: `.venv/Scripts/python.exe -m pytest tests/test_matrix_questions.py -v`
Expected: FAIL — `matrix_analytics` module and `matrix` type marker don't exist.

### Step 3: Add matrix to upload contract

In `src/game_survey_workbench/services/upload_contract.py`:

```python
ALLOWED_TYPE_MARKERS = {
    "metadata",
    "single_choice",
    "multi_select",
    "free_text",
    "scale",
    "matrix",
    "ranking",
}
```

### Step 4: Implement matrix analytics service

```python
# src/game_survey_workbench/services/matrix_analytics.py
from __future__ import annotations

import pandas as pd


def detect_matrix_group(columns: list[str], prefix: str) -> list[str]:
    return [col for col in columns if col.startswith(prefix)]


def summarize_matrix_group(
    *,
    dataframe: pd.DataFrame,
    columns: list[str],
    top_box_values: set[int] | None = None,
) -> dict[str, dict[str, float]]:
    if top_box_values is None:
        top_box_values = {4, 5}

    result: dict[str, dict[str, float]] = {}
    for col in columns:
        if col not in dataframe.columns:
            continue
        series = pd.to_numeric(dataframe[col], errors="coerce").dropna()
        if series.empty:
            result[col] = {"mean": 0.0, "top_box_rate": 0.0, "n": 0}
            continue
        result[col] = {
            "mean": round(float(series.mean()), 3),
            "top_box_rate": round(float(series.isin(top_box_values).mean()), 3),
            "n": int(len(series)),
        }
    return result


def describe_matrix_summary(
    group_label: str,
    summary: dict[str, dict[str, float]],
) -> str:
    lines = [f"Matrix battery '{group_label}':"]
    sorted_items = sorted(summary.items(), key=lambda x: x[1].get("mean", 0), reverse=True)
    for col, stats in sorted_items:
        lines.append(
            f"  {col}: mean {stats['mean']:.3f}, "
            f"top-box {stats['top_box_rate'] * 100:.1f}%, "
            f"n={int(stats.get('n', 0))}"
        )
    if sorted_items:
        best = sorted_items[0]
        worst = sorted_items[-1]
        gap = best[1]["mean"] - worst[1]["mean"]
        lines.append(
            f"  Spread: '{best[0]}' leads by {gap:.3f} over '{worst[0]}'"
        )
    return "\n".join(lines)
```

### Step 5: Wire matrix into deterministic findings

In `services/analysis_context.py`, add matrix handling to `build_deterministic_findings_for_run`:

```python
# After the existing question_type dispatching, add:
elif question_schema.question_type == "matrix":
    from game_survey_workbench.services.matrix_analytics import (
        detect_matrix_group,
        summarize_matrix_group,
        describe_matrix_summary,
    )
    # Matrix columns share a prefix like "Q5_"
    prefix = question_column.rsplit("_", 1)[0] + "_"
    group_cols = detect_matrix_group(
        list(context.dataframe.columns), prefix=prefix,
    )
    if group_cols and question_column == group_cols[0]:
        # Only summarize once per matrix group (triggered by first column)
        matrix_summary = summarize_matrix_group(
            dataframe=context.dataframe,
            columns=group_cols,
            top_box_values={4, 5},
        )
        finding = describe_matrix_summary(prefix.rstrip("_"), matrix_summary)
        if finding:
            findings.append(finding)
```

### Step 6: Run test to verify it passes

Run: `.venv/Scripts/python.exe -m pytest tests/test_matrix_questions.py -v`
Expected: 4 passed

### Step 7: Run full regression

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: all previous + 4 new pass

### Step 8: Commit

```bash
git add src/game_survey_workbench/services/upload_contract.py src/game_survey_workbench/services/matrix_analytics.py src/game_survey_workbench/services/analysis_context.py tests/test_matrix_questions.py
git commit -m "feat(stage4b): add matrix question type with battery summarization and deterministic findings"
```

---

## Task 3: Ranking question type support (Stage 4C)

**Files:**
- Create: `src/game_survey_workbench/services/ranking_analytics.py`
- Modify: `src/game_survey_workbench/services/analysis_context.py`
- Create: `tests/test_ranking_questions.py`

### Step 1: Write the failing test

```python
# tests/test_ranking_questions.py
import pandas as pd

from game_survey_workbench.services.ranking_analytics import (
    normalize_ranking_data,
    summarize_ranking,
    describe_ranking_summary,
)


def test_normalize_ranking_columns():
    """Ranking data: each column is a rank position, value is the item placed there."""
    df = pd.DataFrame({
        "Q7_Rank1": ["Graphics", "Sound", "Graphics"],
        "Q7_Rank2": ["Sound", "Graphics", "Controls"],
        "Q7_Rank3": ["Controls", "Controls", "Sound"],
    })
    normalized = normalize_ranking_data(
        dataframe=df,
        columns=["Q7_Rank1", "Q7_Rank2", "Q7_Rank3"],
    )
    # Normalized: item -> average rank
    assert "Graphics" in normalized
    assert "Sound" in normalized
    assert "Controls" in normalized
    # Graphics: ranks 1, 2, 1 -> avg 1.333
    assert abs(normalized["Graphics"]["avg_rank"] - 1.333) < 0.01


def test_normalize_ranking_numeric_columns():
    """Alternative: each column is an item, value is its rank."""
    df = pd.DataFrame({
        "Q7_Graphics": [1, 2, 1],
        "Q7_Sound": [2, 1, 3],
        "Q7_Controls": [3, 3, 2],
    })
    normalized = normalize_ranking_data(
        dataframe=df,
        columns=["Q7_Graphics", "Q7_Sound", "Q7_Controls"],
        format="item_as_column",
    )
    assert "Q7_Graphics" in normalized
    assert abs(normalized["Q7_Graphics"]["avg_rank"] - 1.333) < 0.01


def test_summarize_ranking():
    df = pd.DataFrame({
        "Q7_Rank1": ["A", "B", "A", "A"],
        "Q7_Rank2": ["B", "A", "B", "C"],
        "Q7_Rank3": ["C", "C", "C", "B"],
    })
    summary = summarize_ranking(
        dataframe=df,
        columns=["Q7_Rank1", "Q7_Rank2", "Q7_Rank3"],
    )
    # A should be ranked best (lowest avg rank)
    items_by_rank = sorted(summary.items(), key=lambda x: x[1]["avg_rank"])
    assert items_by_rank[0][0] == "A"


def test_describe_ranking():
    df = pd.DataFrame({
        "Q7_Rank1": ["A", "B"],
        "Q7_Rank2": ["B", "A"],
    })
    summary = summarize_ranking(
        dataframe=df,
        columns=["Q7_Rank1", "Q7_Rank2"],
    )
    text = describe_ranking_summary("Feature Priority", summary)
    assert "Feature Priority" in text
    assert "A" in text
```

### Step 2: Run test to verify it fails

Run: `.venv/Scripts/python.exe -m pytest tests/test_ranking_questions.py -v`
Expected: FAIL — module does not exist.

### Step 3: Implement ranking analytics

```python
# src/game_survey_workbench/services/ranking_analytics.py
from __future__ import annotations

import pandas as pd


def normalize_ranking_data(
    *,
    dataframe: pd.DataFrame,
    columns: list[str],
    format: str = "rank_as_column",
) -> dict[str, dict[str, float]]:
    """Normalize ranking data into item -> {avg_rank, first_place_count, n}.

    Two formats:
    - rank_as_column: columns are Rank1, Rank2...; values are item names
    - item_as_column: columns are item names; values are rank numbers
    """
    item_ranks: dict[str, list[float]] = {}

    if format == "item_as_column":
        for col in columns:
            if col not in dataframe.columns:
                continue
            ranks = pd.to_numeric(dataframe[col], errors="coerce").dropna()
            item_ranks[col] = ranks.tolist()
    else:
        for rank_idx, col in enumerate(columns, start=1):
            if col not in dataframe.columns:
                continue
            for item in dataframe[col].dropna().astype(str):
                item_ranks.setdefault(item, []).append(float(rank_idx))

    result: dict[str, dict[str, float]] = {}
    for item, ranks in item_ranks.items():
        result[item] = {
            "avg_rank": round(sum(ranks) / len(ranks), 3) if ranks else 0.0,
            "first_place_count": sum(1 for r in ranks if r == 1.0),
            "n": len(ranks),
        }
    return result


def summarize_ranking(
    *,
    dataframe: pd.DataFrame,
    columns: list[str],
    format: str = "rank_as_column",
) -> dict[str, dict[str, float]]:
    return normalize_ranking_data(dataframe=dataframe, columns=columns, format=format)


def describe_ranking_summary(
    label: str,
    summary: dict[str, dict[str, float]],
) -> str:
    lines = [f"Ranking '{label}':"]
    sorted_items = sorted(summary.items(), key=lambda x: x[1]["avg_rank"])
    for rank, (item, stats) in enumerate(sorted_items, start=1):
        lines.append(
            f"  #{rank} {item}: avg rank {stats['avg_rank']:.3f}, "
            f"first-place {int(stats['first_place_count'])}x, "
            f"n={int(stats['n'])}"
        )
    return "\n".join(lines)
```

### Step 4: Wire ranking into deterministic findings

In `services/analysis_context.py`, add ranking handling:

```python
elif question_schema.question_type == "ranking":
    from game_survey_workbench.services.ranking_analytics import (
        summarize_ranking,
        describe_ranking_summary,
    )
    # Ranking columns share a prefix like "Q7_Rank"
    prefix = question_column.rsplit("_", 1)[0] + "_"
    rank_cols = [c for c in context.dataframe.columns if c.startswith(prefix)]
    if rank_cols and question_column == rank_cols[0]:
        ranking_summary = summarize_ranking(
            dataframe=context.dataframe,
            columns=rank_cols,
        )
        finding = describe_ranking_summary(prefix.rstrip("_"), ranking_summary)
        if finding:
            findings.append(finding)
```

### Step 5: Run test to verify it passes

Run: `.venv/Scripts/python.exe -m pytest tests/test_ranking_questions.py -v`
Expected: 4 passed

### Step 6: Run full regression

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: all pass

### Step 7: Commit

```bash
git add src/game_survey_workbench/services/ranking_analytics.py src/game_survey_workbench/services/analysis_context.py tests/test_ranking_questions.py
git commit -m "feat(stage4c): add ranking question type with normalization and deterministic findings"
```

---

## Task 4: Enhanced recommendation logic in insight synthesis (Stage 4D)

**Files:**
- Modify: `src/game_survey_workbench/llm/prompts/insight_synthesis.md`
- Create: `src/game_survey_workbench/services/recommendation.py`
- Modify: `src/game_survey_workbench/services/insights.py`
- Create: `tests/test_recommendation.py`

### Step 1: Write the failing test

```python
# tests/test_recommendation.py
from game_survey_workbench.services.recommendation import (
    build_recommendation_context,
    format_findings_for_recommendation,
)


def test_build_recommendation_context_includes_all_signal_types():
    context = build_recommendation_context(
        research_goal="Evaluate event satisfaction",
        statistical_findings=["Q3 top box dropped to 32%"],
        crosstab_findings=["Satisfaction by Segment: Whales 85%, Minnows 40%"],
        coded_themes=["Rewards feel too random (n=12)"],
        matrix_findings=["Q5 battery: Graphics leads, Sound trails by 1.2"],
        brief_objectives=["Identify friction points", "Measure perceived value"],
    )
    assert "Q3 top box dropped to 32%" in context
    assert "Whales 85%" in context
    assert "Rewards feel too random" in context
    assert "Graphics leads" in context
    assert "Identify friction points" in context


def test_format_findings_groups_by_type():
    formatted = format_findings_for_recommendation(
        statistical_findings=["Mean 3.5"],
        crosstab_findings=["Payer vs Free gap: 1.2"],
        coded_themes=["Pacing concern (n=8)"],
    )
    assert "Statistical Findings" in formatted
    assert "Cross-tabulation" in formatted
    assert "Open-text Themes" in formatted


def test_recommendation_context_works_without_optional_fields():
    context = build_recommendation_context(
        research_goal="Basic study",
        statistical_findings=["Mean 4.0"],
    )
    assert "Basic study" in context
    assert "Mean 4.0" in context
```

### Step 2: Run test to verify it fails

Run: `.venv/Scripts/python.exe -m pytest tests/test_recommendation.py -v`
Expected: FAIL — module does not exist.

### Step 3: Implement recommendation service

```python
# src/game_survey_workbench/services/recommendation.py
from __future__ import annotations


def format_findings_for_recommendation(
    *,
    statistical_findings: list[str] | None = None,
    crosstab_findings: list[str] | None = None,
    coded_themes: list[str] | None = None,
    matrix_findings: list[str] | None = None,
    ranking_findings: list[str] | None = None,
) -> str:
    sections: list[str] = []

    if statistical_findings:
        sections.append("### Statistical Findings")
        sections.extend(f"- {f}" for f in statistical_findings)

    if crosstab_findings:
        sections.append("### Cross-tabulation Findings")
        sections.extend(f"- {f}" for f in crosstab_findings)

    if matrix_findings:
        sections.append("### Matrix Battery Findings")
        sections.extend(f"- {f}" for f in matrix_findings)

    if ranking_findings:
        sections.append("### Ranking Findings")
        sections.extend(f"- {f}" for f in ranking_findings)

    if coded_themes:
        sections.append("### Open-text Themes")
        sections.extend(f"- {f}" for f in coded_themes)

    return "\n".join(sections)


def build_recommendation_context(
    *,
    research_goal: str,
    statistical_findings: list[str] | None = None,
    crosstab_findings: list[str] | None = None,
    coded_themes: list[str] | None = None,
    matrix_findings: list[str] | None = None,
    ranking_findings: list[str] | None = None,
    brief_objectives: list[str] | None = None,
    knowledge_snippets: list[str] | None = None,
) -> str:
    parts: list[str] = [f"Research Goal: {research_goal}"]

    if brief_objectives:
        parts.append("Research Objectives:")
        parts.extend(f"- {obj}" for obj in brief_objectives)

    findings_text = format_findings_for_recommendation(
        statistical_findings=statistical_findings or [],
        crosstab_findings=crosstab_findings or [],
        coded_themes=coded_themes or [],
        matrix_findings=matrix_findings or [],
        ranking_findings=ranking_findings or [],
    )
    if findings_text:
        parts.append("")
        parts.append("## Evidence Base")
        parts.append(findings_text)

    if knowledge_snippets:
        parts.append("")
        parts.append("## Relevant Knowledge")
        parts.extend(f"- {s}" for s in knowledge_snippets)

    return "\n".join(parts)
```

### Step 4: Update insight synthesis prompt

Replace the content of `src/game_survey_workbench/llm/prompts/insight_synthesis.md`:

```markdown
# Insight Synthesis Prompt

Write Markdown insight synthesis for a game survey analysis workflow.

## Input

- Research goal and objectives (from project brief)
- Statistical findings (deterministic, pre-computed)
- Cross-tabulation findings (segment-level comparisons)
- Matrix battery findings (multi-item satisfaction/rating comparisons)
- Ranking findings (item priority orderings)
- Coded open-text themes (from prior coding step)
- Retrieved knowledge snippets (from project knowledge base)

## Output Structure

### 1. Executive Takeaway (1-2 sentences)

Open with the single most important finding that a decision-maker needs to hear. Ground it in a specific stat or coded theme.

### 2. Supporting Analysis (2-4 paragraphs)

- Connect statistical findings, cross-tabulation patterns, coded themes, and knowledge where they reinforce each other.
- When cross-tab data reveals a segment gap, call out the magnitude and the affected segment explicitly.
- When matrix batteries show item-level spread, highlight the strongest and weakest items and the gap size.
- Use brief inline citations - e.g., "(per Churn Framework)" or "(coded theme: Boredom, n=12)" - rather than pasting long excerpts.
- Call out contradictions or gaps explicitly rather than ignoring them.

### 3. Recommended Actions (3-5 bullets)

- Each recommendation must be tied to a specific finding (stat, cross-tab, coded theme, or knowledge source).
- Frame recommendations as "Consider X because Y (evidence: Z)" rather than vague "improve the experience."
- Prioritize recommendations by expected impact, not by order of appearance in findings.
- Where cross-tab data shows a segment-specific problem, target the recommendation to that segment.
- Where matrix data reveals a weak item, recommend investigation or action on that specific item.

### 4. Open Questions (1-3 bullets, optional)

- Flag areas where the data is insufficient to draw a conclusion.
- Suggest follow-up research or data collection that would resolve the ambiguity.

## Constraints

- Every claim must point back to a stat finding, cross-tab pattern, coded theme, or knowledge source.
- Do not fabricate evidence.
- Keep the output in Markdown prose suitable for a report section.
- Be concise - the full narrative should fit in roughly 300-500 words.
```

### Step 5: Run test to verify it passes

Run: `.venv/Scripts/python.exe -m pytest tests/test_recommendation.py -v`
Expected: 3 passed

### Step 6: Run full regression

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: all pass (existing insight tests use the function signature unchanged)

### Step 7: Commit

```bash
git add src/game_survey_workbench/services/recommendation.py src/game_survey_workbench/llm/prompts/insight_synthesis.md src/game_survey_workbench/services/insights.py tests/test_recommendation.py
git commit -m "feat(stage4d): add recommendation context builder and strengthen insight synthesis prompt"
```

---

## Task 5: Report-to-knowledge feedback loop (Stage 4E)

**Files:**
- Create: `src/game_survey_workbench/services/knowledge_feedback.py`
- Modify: `src/game_survey_workbench/routes/reports.py`
- Create: `tests/test_knowledge_feedback.py`

### Step 1: Write the failing test

```python
# tests/test_knowledge_feedback.py
from pathlib import Path

import pytest

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.knowledge_feedback import (
    save_report_findings_as_knowledge,
    KnowledgeFeedbackPayload,
)
from game_survey_workbench.services.knowledge_parser import parse_markdown_document


def test_save_findings_creates_knowledge_file(tmp_path: Path):
    create_project(
        ProjectCreate(slug="bp-study", name="BP Study"),
        workspace_root=tmp_path,
    )
    payload = KnowledgeFeedbackPayload(
        project_slug="bp-study",
        title="BP Study Key Findings",
        key_findings=[
            "Pass conversion dropped 12% among mid-tier payers",
            "Reward preview clarity was the top coded complaint",
        ],
        recommendations=[
            "Add value comparison tooltip on pass purchase screen",
        ],
        source_report_path="reports/report-2026-03-15.md",
    )
    result = save_report_findings_as_knowledge(
        payload=payload,
        workspace_root=tmp_path,
    )
    assert result.file_path.exists()
    assert result.file_path.suffix == ".md"

    # The saved file should be valid knowledge with frontmatter
    content = result.file_path.read_text(encoding="utf-8")
    doc = parse_markdown_document(content)
    assert doc.doc_type == "experience"
    assert "analysis" in doc.stages
    assert "BP Study" in doc.title or "BP Study" in doc.body
    assert "12%" in doc.body


def test_saved_knowledge_includes_source_reference(tmp_path: Path):
    create_project(
        ProjectCreate(slug="bp-study", name="BP Study"),
        workspace_root=tmp_path,
    )
    payload = KnowledgeFeedbackPayload(
        project_slug="bp-study",
        title="BP Study Learnings",
        key_findings=["Finding A"],
        source_report_path="reports/report-2026-03-15.md",
    )
    result = save_report_findings_as_knowledge(
        payload=payload,
        workspace_root=tmp_path,
    )
    content = result.file_path.read_text(encoding="utf-8")
    assert "report-2026-03-15" in content


def test_feedback_without_recommendations(tmp_path: Path):
    create_project(
        ProjectCreate(slug="bp-study", name="BP Study"),
        workspace_root=tmp_path,
    )
    payload = KnowledgeFeedbackPayload(
        project_slug="bp-study",
        title="Minimal Feedback",
        key_findings=["One finding"],
    )
    result = save_report_findings_as_knowledge(
        payload=payload,
        workspace_root=tmp_path,
    )
    assert result.file_path.exists()
```

### Step 2: Run test to verify it fails

Run: `.venv/Scripts/python.exe -m pytest tests/test_knowledge_feedback.py -v`
Expected: FAIL — module does not exist.

### Step 3: Implement knowledge feedback service

```python
# src/game_survey_workbench/services/knowledge_feedback.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel


class KnowledgeFeedbackPayload(BaseModel):
    project_slug: str
    title: str
    key_findings: list[str]
    recommendations: list[str] | None = None
    source_report_path: str = ""


@dataclass
class KnowledgeFeedbackResult:
    file_path: Path
    document_title: str


def save_report_findings_as_knowledge(
    *,
    payload: KnowledgeFeedbackPayload,
    workspace_root: Path,
) -> KnowledgeFeedbackResult:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d")
    slug = payload.project_slug
    filename = f"{slug}-findings-{timestamp}.md"

    knowledge_dir = workspace_root / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    file_path = knowledge_dir / filename

    frontmatter_lines = [
        "---",
        f"title: {payload.title}",
        "doc_type: experience",
        "stage:",
        "  - analysis",
        "  - report",
        "tags:",
        f"  - {slug}",
        "  - findings",
        f"scenario: {slug}",
        "priority: high",
        "---",
    ]

    body_lines = [
        f"# {payload.title}",
        "",
        f"Source project: {slug}",
    ]
    if payload.source_report_path:
        body_lines.append(f"Source report: {payload.source_report_path}")
    body_lines.append(f"Date: {timestamp}")
    body_lines.append("")

    body_lines.append("## Key Findings")
    body_lines.append("")
    for finding in payload.key_findings:
        body_lines.append(f"- {finding}")
    body_lines.append("")

    if payload.recommendations:
        body_lines.append("## Recommendations")
        body_lines.append("")
        for rec in payload.recommendations:
            body_lines.append(f"- {rec}")
        body_lines.append("")

    content = "\n".join(frontmatter_lines) + "\n" + "\n".join(body_lines)
    file_path.write_text(content, encoding="utf-8")

    return KnowledgeFeedbackResult(
        file_path=file_path,
        document_title=payload.title,
    )
```

### Step 4: Add route

In `src/game_survey_workbench/routes/reports.py`, add:

```python
from game_survey_workbench.services.knowledge_feedback import (
    KnowledgeFeedbackPayload,
    save_report_findings_as_knowledge,
)

@router.post("/reports/feedback-to-knowledge")
def feedback_to_knowledge(payload: KnowledgeFeedbackPayload):
    settings = get_settings()
    result = save_report_findings_as_knowledge(
        payload=payload,
        workspace_root=settings.workspace_root,
    )
    return {
        "file_path": str(result.file_path),
        "document_title": result.document_title,
    }
```

### Step 5: Run test to verify it passes

Run: `.venv/Scripts/python.exe -m pytest tests/test_knowledge_feedback.py -v`
Expected: 3 passed

### Step 6: Run full regression

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: all pass

### Step 7: Commit

```bash
git add src/game_survey_workbench/services/knowledge_feedback.py src/game_survey_workbench/routes/reports.py tests/test_knowledge_feedback.py
git commit -m "feat(stage4e): add report-to-knowledge feedback loop for experience-layer persistence"
```

---

## Task 6: Update north-star document (Stage 4F)

**Files:**
- Modify: `docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md`

### Step 1: Add Stage 4 status section

Append to the "Current Stage Status" section:

```markdown
As of 2026-03-15, the roadmap status within Stage 4 is:

- Stage 4A `Cross-tabulation Analytics Engine`: not started
- Stage 4B `Matrix Question Type Support`: not started
- Stage 4C `Ranking Question Type Support`: not started
- Stage 4D `Enhanced Recommendation Logic`: not started
- Stage 4E `Report-to-Knowledge Feedback Loop`: not started
```

### Step 2: Update "Next Planned Artifact" and "After Stage 3"

Update the north-star to reflect Stage 4 is now in planning and execution.

### Step 3: Run full regression

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 113+ tests pass (document changes don't affect tests)

### Step 4: Commit

```bash
git add docs/plans/2026-03-13-game-survey-workbench-north-star-plan.md
git commit -m "docs: update north-star with Stage 4 sub-stage breakdown and status tracking"
```

---

## Acceptance criteria

Stage 4 is complete when:

1. `compute_crosstab` works for categorical × categorical and scale × categorical combinations
2. `describe_crosstab` produces readable segment comparison text
3. Cross-tab route (`POST /crosstabs`) returns table and group summaries from a live analysis run
4. `build_crosstab_findings_for_run` auto-generates cross-tab findings for insight context
5. `matrix` type marker is accepted by the upload contract
6. Matrix battery summarization computes per-item mean/top-box with spread analysis
7. `ranking` type marker is accepted by the upload contract
8. Ranking normalization handles both "rank-as-column" and "item-as-column" formats
9. `build_recommendation_context` assembles all finding types into structured LLM context
10. Insight synthesis prompt explicitly asks for cross-tab, matrix, and ranking evidence
11. `save_report_findings_as_knowledge` persists findings as experience-layer Markdown with proper frontmatter
12. All new code has regression tests
13. Full test suite passes (113+ existing + new Stage 4 tests)
14. North-star document updated with Stage 4 sub-stage status

## Out of scope for Stage 4

- Statistical significance testing (chi-square, t-test, ANOVA)
- Visualization / chart generation
- Multi-dataset comparison across projects
- Automated cohort discovery
- Embedding-based semantic retrieval upgrade
- Form-based UI for cross-tab configuration
- Knowledge feedback auto-ingestion (the file is saved; ingestion is a manual step)

## Dependency map

```
Task 1 (4A: Cross-tabulation)
  └── Task 4 (4D: Recommendation context uses crosstab findings)

Task 2 (4B: Matrix questions)
  └── Task 4 (4D: Recommendation context uses matrix findings)

Task 3 (4C: Ranking questions)
  └── Task 4 (4D: Recommendation context uses ranking findings)

Task 4 (4D: Recommendation logic) — depends on Tasks 1-3

Task 5 (4E: Knowledge feedback) — independent, can run any time

Task 6 (4F: North-star update) — independent, can run any time
```

Parallelizable: Tasks 1, 2, 3, 5 can be implemented concurrently. Task 4 depends on Tasks 1-3. Task 6 is independent.

## Risks

| Risk | Mitigation |
|------|-----------|
| Matrix column grouping heuristic (prefix-based) may not match all real survey formats | The `detect_matrix_group` function accepts an explicit prefix; the upload contract's dual-header format lets users declare `matrix` type per column, bypassing heuristics |
| Ranking data comes in two incompatible formats (rank-as-column vs item-as-column) | Both formats are supported with an explicit `format` parameter; the upload contract can evolve to declare format per question group |
| Cross-tab on large datasets with many categories may produce unwieldy output | The `describe_crosstab` function only reports the top category per segment; full tables are available via the API response but not injected into LLM context |
| Knowledge feedback files accumulate without curation | Files are saved to `knowledge/` but require manual ingestion; this is intentional — automatic ingestion risks polluting the knowledge base with noisy findings |
| Insight synthesis prompt length may grow with 5 finding types | The `format_findings_for_recommendation` function structures findings into labeled sections; the prompt constrains output to 300-500 words regardless of input length |

## Quick-start instructions for a new agent session

```
仓库路径：C:\Users\69050\Documents\Playground
基于当前本地 master 工作，Stage 3 已完成，113 tests passing。
请执行 docs/plans/2026-03-15-game-survey-workbench-stage-4-advanced-research-plan.md
从 Task 1 开始，逐个执行。
```
