from __future__ import annotations

from dataclasses import dataclass
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
    "ranking",
}


@dataclass
class InferredColumn:
    title: str
    inferred_type: str
    confidence: str
    reason: str


@dataclass
class FormatDetectionResult:
    format_type: str
    column_titles: list[str]
    column_types: list[str]
    inferred_columns: list[InferredColumn]
    preview_rows: list[list[str]]


HEADER_KEYWORD_RULES: list[tuple[str, str, str]] = [
    ("（多选）", "multi_select", "Header contains 问卷星 multi-select marker '（多选）'"),
    ("（填空）", "free_text", "Header contains 问卷星 free-text marker '（填空）'"),
    ("(多选)", "multi_select", "Header contains multi-select marker '(多选)'"),
    ("(填空)", "free_text", "Header contains free-text marker '(填空)'"),
    ("multiple choices", "multi_select", "Header contains 'Multiple Choices'"),
    ("open-ended response", "free_text", "Header contains SurveyMonkey 'Open-Ended Response'"),
    ("feel free", "free_text", "Header contains 'feel free' suggesting open text"),
    ("suggestion", "free_text", "Header contains 'suggestion' suggesting open text"),
]


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


def detect_format(path: Path) -> FormatDetectionResult:
    raw = _load_raw_tabular_file(path)
    if len(raw.index) < 2:
        raise ValueError("File has fewer than 2 rows; cannot detect format.")

    column_titles = raw.iloc[0].fillna("").astype(str).tolist()
    candidate_types = raw.iloc[1].fillna("").astype(str).str.strip().tolist()

    if all(marker in ALLOWED_TYPE_MARKERS for marker in candidate_types):
        data_rows = raw.iloc[2:]
        preview = data_rows.head(5).fillna("").astype(str).values.tolist()
        return FormatDetectionResult(
            format_type="dual_header",
            column_titles=column_titles,
            column_types=candidate_types,
            inferred_columns=[],
            preview_rows=preview,
        )

    data_rows = raw.iloc[1:].copy()
    data_rows.columns = column_titles
    data_rows = data_rows.reset_index(drop=True)
    preview = data_rows.head(5).fillna("").astype(str).values.tolist()

    inferred_columns: list[InferredColumn] = []
    for column_title in column_titles:
        inferred_type, confidence, reason = _infer_column_type(column_title, data_rows[column_title])
        inferred_columns.append(
            InferredColumn(
                title=column_title,
                inferred_type=inferred_type,
                confidence=confidence,
                reason=reason,
            )
        )

    return FormatDetectionResult(
        format_type="single_header",
        column_titles=column_titles,
        column_types=[column.inferred_type for column in inferred_columns],
        inferred_columns=inferred_columns,
        preview_rows=preview,
    )


def _infer_column_type(header: str, series: pd.Series) -> tuple[str, str, str]:
    lowered = header.lower()
    for keyword, column_type, reason in HEADER_KEYWORD_RULES:
        if keyword.lower() in lowered:
            return column_type, "high", reason

    from game_survey_workbench.services.dataset_import import (
        _average_text_length,
        _numeric_density,
        _separator_density,
    )

    separator_density = _separator_density(series)
    if separator_density >= 0.5:
        return "multi_select", "high", f"Separator density {separator_density:.0%} >= 50%"

    numeric_density = _numeric_density(series)
    if numeric_density >= 0.8:
        return "scale", "high", f"Numeric density {numeric_density:.0%} >= 80%"

    average_text_length = _average_text_length(series)
    if average_text_length >= 25 and numeric_density < 0.3:
        return "free_text", "medium", f"Average text length {average_text_length:.0f} chars, low numeric density"

    non_null = series.dropna()
    unique_ratio = non_null.nunique() / max(len(non_null), 1)
    if unique_ratio <= 0.3:
        return "single_choice", "medium", f"Low unique ratio {unique_ratio:.0%} suggests categorical"

    return "single_choice", "low", "Default fallback — could not determine type with confidence"


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
