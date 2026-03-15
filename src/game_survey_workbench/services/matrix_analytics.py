from __future__ import annotations

import pandas as pd


def detect_matrix_group(columns: list[str], prefix: str) -> list[str]:
    return [column for column in columns if column.startswith(prefix)]


def summarize_matrix_group(
    *,
    dataframe: pd.DataFrame,
    columns: list[str],
    top_box_values: set[int] | None = None,
) -> dict[str, dict[str, float]]:
    if top_box_values is None:
        top_box_values = {4, 5}

    summary: dict[str, dict[str, float]] = {}
    for column in columns:
        if column not in dataframe.columns:
            continue
        series = pd.to_numeric(dataframe[column], errors="coerce").dropna()
        if series.empty:
            summary[column] = {"mean": 0.0, "top_box_rate": 0.0, "n": 0}
            continue
        summary[column] = {
            "mean": round(float(series.mean()), 3),
            "top_box_rate": round(float(series.isin(top_box_values).mean()), 3),
            "n": int(len(series)),
        }
    return summary


def describe_matrix_summary(
    group_label: str,
    summary: dict[str, dict[str, float]],
) -> str:
    lines = [f"Matrix battery '{group_label}':"]
    sorted_items = sorted(
        summary.items(),
        key=lambda item: item[1].get("mean", 0.0),
        reverse=True,
    )
    for column, stats in sorted_items:
        lines.append(
            f"  {column}: mean {stats['mean']:.3f}, "
            f"top-box {stats['top_box_rate'] * 100:.1f}%, "
            f"n={int(stats.get('n', 0))}"
        )
    if sorted_items:
        best = sorted_items[0]
        worst = sorted_items[-1]
        lines.append(
            f"  Spread: '{best[0]}' leads by {best[1]['mean'] - worst[1]['mean']:.3f} over '{worst[0]}'"
        )
    return "\n".join(lines)
