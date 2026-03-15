from __future__ import annotations

import pandas as pd


def normalize_ranking_data(
    *,
    dataframe: pd.DataFrame,
    columns: list[str],
    format: str = "rank_as_column",
) -> dict[str, dict[str, float]]:
    item_ranks: dict[str, list[float]] = {}

    if format == "item_as_column":
        for column in columns:
            if column not in dataframe.columns:
                continue
            ranks = pd.to_numeric(dataframe[column], errors="coerce").dropna()
            item_ranks[column] = ranks.tolist()
    else:
        for rank_index, column in enumerate(columns, start=1):
            if column not in dataframe.columns:
                continue
            for item in dataframe[column].dropna().astype(str):
                item_ranks.setdefault(item, []).append(float(rank_index))

    summary: dict[str, dict[str, float]] = {}
    for item, ranks in item_ranks.items():
        summary[item] = {
            "avg_rank": round(sum(ranks) / len(ranks), 3) if ranks else 0.0,
            "first_place_count": sum(1 for rank in ranks if rank == 1.0),
            "n": len(ranks),
        }
    return summary


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
    sorted_items = sorted(summary.items(), key=lambda item: item[1]["avg_rank"])
    for rank, (item, stats) in enumerate(sorted_items, start=1):
        lines.append(
            f"  #{rank} {item}: avg rank {stats['avg_rank']:.3f}, "
            f"first-place {int(stats['first_place_count'])}x, "
            f"n={int(stats['n'])}"
        )
    return "\n".join(lines)
