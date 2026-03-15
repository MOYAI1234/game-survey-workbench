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
    if row_column not in dataframe.columns:
        raise ValueError(f"Cross-tab row column '{row_column}' not found.")
    if col_column not in dataframe.columns:
        raise ValueError(f"Cross-tab column '{col_column}' not found.")
    if top_box_values is None:
        top_box_values = {4, 5}

    working = dataframe[[row_column, col_column]].dropna()
    if working.empty:
        raise ValueError(
            f"Cross-tab input is empty after dropping nulls from '{row_column}' x '{col_column}'."
        )

    col_values = sorted(working[col_column].astype(str).unique().tolist())
    row_values = sorted(working[row_column].astype(str).unique().tolist())
    table: dict[str, dict[str, dict[str, float]]] = {}
    group_summaries: dict[str, dict[str, float]] = {}

    col_series = working[col_column].astype(str)
    row_series = working[row_column]
    for col_value in col_values:
        subset = row_series.loc[col_series == col_value]
        total = len(subset)

        if row_type == "scale":
            numeric = pd.to_numeric(subset, errors="coerce").dropna()
            group_summaries[col_value] = {
                "mean": round(float(numeric.mean()), 3) if not numeric.empty else 0.0,
                "top_box_rate": round(float(numeric.isin(top_box_values).mean()), 3)
                if not numeric.empty
                else 0.0,
                "n": int(total),
            }
            continue

        counts = subset.astype(str).value_counts()
        distribution: dict[str, dict[str, float]] = {}
        for row_value in row_values:
            count = int(counts.get(row_value, 0))
            distribution[row_value] = {
                "count": count,
                "percentage": round(count / total, 3) if total else 0.0,
            }
        table[col_value] = distribution

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
        for col_value, summary in result.group_summaries.items():
            lines.append(
                f"  {col_value}: mean {summary.get('mean', 0):.3f}, "
                f"top-box {summary.get('top_box_rate', 0) * 100:.1f}%, "
                f"n={int(summary.get('n', 0))}"
            )
        return "\n".join(lines)

    for col_value, distribution in result.table.items():
        top_row = max(distribution.items(), key=lambda item: item[1]["count"])
        lines.append(
            f"  {col_value}: top '{top_row[0]}' "
            f"({int(top_row[1]['count'])} responses, {top_row[1]['percentage'] * 100:.1f}%)"
        )
    return "\n".join(lines)
