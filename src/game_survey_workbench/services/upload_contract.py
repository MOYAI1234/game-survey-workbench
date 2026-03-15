from __future__ import annotations

from pathlib import Path

import pandas as pd
from pydantic import ConfigDict
from sqlmodel import SQLModel


ALLOWED_TYPE_MARKERS = {
    "metadata",
    "single_choice",
    "multi_select",
    "free_text",
    "scale",
    "matrix",
}


class ParsedDualHeaderDataset(SQLModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    column_titles: list[str]
    column_types: list[str]
    dataframe: pd.DataFrame


def _load_raw_tabular_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, header=None)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, header=None)
    raise ValueError(f"Unsupported dataset format: {path.suffix}")


def parse_dual_header_dataframe(path: Path) -> ParsedDualHeaderDataset:
    raw = _load_raw_tabular_file(path)
    if len(raw.index) < 3:
        raise ValueError("Missing type marker row. Row 2 must define a type for every column.")

    column_titles = raw.iloc[0].fillna("").astype(str).tolist()
    column_types = raw.iloc[1].fillna("").astype(str).tolist()
    for index, marker in enumerate(column_types, start=1):
        normalized = marker.strip()
        if not normalized:
            title = column_titles[index - 1] or f"column {index}"
            raise ValueError(f"Column '{title}' is missing a type marker in row 2.")
        if normalized not in ALLOWED_TYPE_MARKERS:
            raise ValueError(f"Unsupported type marker '{normalized}' in column {index}.")
        column_types[index - 1] = normalized

    dataframe = raw.iloc[2:].copy()
    dataframe.columns = column_titles
    dataframe = dataframe.reset_index(drop=True)
    return ParsedDualHeaderDataset(
        column_titles=column_titles,
        column_types=column_types,
        dataframe=dataframe,
    )
