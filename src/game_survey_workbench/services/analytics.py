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
