"""Extract dataset metadata summaries for report context."""

from __future__ import annotations

from collections import Counter


def extract_dataset_meta(*, schema: dict, row_count: int) -> dict:
    """Summarize dataset schema into report-ready metadata."""

    columns = schema.get("columns", {})
    type_counts: Counter[str] = Counter()

    for column_info in columns.values():
        question_type = (
            column_info.get("type", "unknown")
            if isinstance(column_info, dict)
            else "unknown"
        )
        type_counts[question_type] += 1

    return {
        "row_count": row_count,
        "question_count": len(columns),
        "question_types": dict(type_counts),
    }
