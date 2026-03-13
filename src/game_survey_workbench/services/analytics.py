from __future__ import annotations

import pandas as pd

from game_survey_workbench.models.analysis import ScaleSummary


def summarize_scale_question(series, top_box_values: set[int]):
    clean = series.dropna().astype(float)
    return ScaleSummary(
        mean=round(float(clean.mean()), 3),
        top_box_rate=round(float(clean.isin(top_box_values).mean()), 3),
    )


def summarize_single_choice(series: pd.Series) -> dict[str, dict[str, float]]:
    clean = series.dropna().astype(str)
    total = len(clean)
    counts = clean.value_counts().to_dict()
    return {
        key: {
            "count": float(value),
            "percentage": round(value / total, 3) if total else 0.0,
        }
        for key, value in counts.items()
    }


def summarize_multi_select(series: pd.Series, separator: str = ";") -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw in series.dropna().astype(str):
        for item in [part.strip() for part in raw.split(separator) if part.strip()]:
            counts[item] = counts.get(item, 0) + 1
    return counts


def describe_scale_summary(question: str, series, top_box_values: set[int]) -> str | None:
    clean = pd.to_numeric(series.dropna(), errors="coerce").dropna()
    if clean.empty:
        return None
    summary = summarize_scale_question(clean, top_box_values=top_box_values)
    return (
        f"{question}: mean {summary.mean:.3f}; "
        f"Top box {(summary.top_box_rate * 100):.1f}%"
    )


def describe_single_choice_summary(question: str, series: pd.Series) -> str | None:
    summary = summarize_single_choice(series)
    if not summary:
        return None
    top_choice, details = max(summary.items(), key=lambda item: item[1]["count"])
    return (
        f"{question}: top choice '{top_choice}' "
        f"({int(details['count'])} responses, {details['percentage'] * 100:.1f}%)"
    )


def describe_multi_select_summary(question: str, series: pd.Series) -> str | None:
    summary = summarize_multi_select(series)
    if not summary:
        return None
    top_choice, count = max(summary.items(), key=lambda item: item[1])
    return f"{question}: most selected item '{top_choice}' ({count} selections)"
