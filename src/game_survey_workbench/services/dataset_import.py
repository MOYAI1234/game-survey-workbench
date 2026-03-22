from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pandas as pd
from sqlmodel import Session

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.analysis_run import AnalysisRunRecord
from game_survey_workbench.models.dataset import (
    DatasetRecord,
    ImportedDataset,
    QuestionColumnSchema,
)
from game_survey_workbench.services.dataset_schema import classify_column
from game_survey_workbench.services.research_waves import get_current_research_wave
from game_survey_workbench.services.upload_contract import detect_format, parse_dual_header_dataframe
from game_survey_workbench.services.workspace import bootstrap_workspace


MULTI_SELECT_SEPARATORS = (";", "|")


def _clean_text_values(series: pd.Series) -> pd.Series:
    return series.dropna().astype(str).str.strip()


def _numeric_density(series: pd.Series) -> float:
    clean = _clean_text_values(series)
    if clean.empty:
        return 0.0
    numeric = pd.to_numeric(clean, errors="coerce")
    return float(numeric.notna().mean())


def _separator_density(series: pd.Series) -> float:
    clean = _clean_text_values(series)
    if clean.empty:
        return 0.0
    contains_separator = clean.apply(lambda value: any(separator in value for separator in MULTI_SELECT_SEPARATORS))
    return float(contains_separator.mean())


def _average_text_length(series: pd.Series) -> float:
    clean = _clean_text_values(series)
    if clean.empty:
        return 0.0
    return float(clean.str.len().mean())


def detect_question_type(series: pd.Series) -> str:
    if _separator_density(series) >= 0.5:
        return "multi_select"
    numeric_density = _numeric_density(series)
    if numeric_density >= 0.8:
        return "scale"
    if _average_text_length(series) >= 25 and numeric_density < 0.3:
        return "free_text"
    return "single_choice"


def detect_question_type_from_header_and_series(header: str, series: pd.Series) -> str:
    lowered = header.lower()
    if "multiple choices" in lowered:
        return "multi_select"
    if "feel free" in lowered or "suggestion" in lowered:
        return "free_text"
    return detect_question_type(series)


def _load_tabular_file(path: Path, *, header: int | None = 0) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, header=header)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, header=header)
    raise ValueError(f"Unsupported dataset format: {path.suffix}")


def load_imported_dataset_dataframe(path: Path) -> pd.DataFrame:
    raw = _load_tabular_file(path, header=None)
    column_titles = raw.iloc[0].fillna("").astype(str).tolist()
    dataframe = raw.iloc[2:].copy()
    dataframe.columns = column_titles
    return dataframe.reset_index(drop=True)


def import_dataset(csv_path: Path, *, project_slug: str, workspace_root: Path) -> ImportedDataset:
    bootstrap_workspace(workspace_root)
    create_db_and_tables(workspace_root)
    current_wave = get_current_research_wave(
        workspace_root=workspace_root,
        project_slug=project_slug,
    )
    parsed = parse_dual_header_dataframe(csv_path)
    dataframe = parsed.dataframe
    column_types = dict(zip(parsed.column_titles, parsed.column_types, strict=False))

    question_columns: dict[str, QuestionColumnSchema] = {}
    for column in dataframe.columns:
        lowered = column.lower()
        declared_type = column_types[column]
        if declared_type == "metadata" or classify_column(column) == "metadata":
            continue
        if "其他" in column or "other" in lowered:
            continue
        other_column = next(
            (
                candidate
                for candidate in dataframe.columns
                if candidate != column and candidate.startswith(column) and ("其他" in candidate or "other" in candidate.lower())
            ),
            None,
        )
        question_columns[column] = QuestionColumnSchema(
            column_role="question",
            question_type=declared_type,
            include_in_analysis=True,
            other_text_column=other_column,
            reason=None,
        )

    dataset_id = str(uuid4())
    analysis_run_id = str(uuid4())
    imported = ImportedDataset(
        dataset_id=dataset_id,
        project_slug=project_slug,
        source_path=str(csv_path),
        question_columns=question_columns,
        analysis_run_id=analysis_run_id,
    )

    schema_dir = workspace_root / "projects" / project_slug / "data" / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    schema_path = schema_dir / f"{dataset_id}.json"
    schema_payload = {
        key: value.model_dump()
        for key, value in question_columns.items()
    }
    schema_path.write_text(
        json.dumps(schema_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    engine = get_engine(workspace_root)
    with Session(engine) as session:
        record = DatasetRecord(
            dataset_id=dataset_id,
            project_slug=project_slug,
            source_path=str(csv_path),
            dataset_schema=schema_payload,
            analysis_run_id=analysis_run_id,
        )
        session.add(record)
        session.add(
            AnalysisRunRecord(
                analysis_run_id=analysis_run_id,
                project_slug=project_slug,
                wave_id=current_wave.id if current_wave is not None else None,
                dataset_id=dataset_id,
                status="ready",
            )
        )
        session.commit()

    return imported


def import_dataset_with_overrides(
    csv_path: Path,
    *,
    project_slug: str,
    workspace_root: Path,
    column_types: list[str],
    column_include: list[str],
) -> ImportedDataset:
    bootstrap_workspace(workspace_root)
    create_db_and_tables(workspace_root)
    current_wave = get_current_research_wave(
        workspace_root=workspace_root,
        project_slug=project_slug,
    )

    detection = detect_format(csv_path)
    raw = _load_tabular_file(csv_path, header=None)

    column_titles = raw.iloc[0].fillna("").astype(str).tolist()
    if detection.format_type == "dual_header":
        dataframe = raw.iloc[2:].copy()
    else:
        dataframe = raw.iloc[1:].copy()
    dataframe.columns = column_titles
    dataframe = dataframe.reset_index(drop=True)

    included_columns = set(column_include)
    question_columns: dict[str, QuestionColumnSchema] = {}
    for index, column_name in enumerate(column_titles):
        if index >= len(column_types):
            break
        declared_type = column_types[index]
        if declared_type == "metadata" or column_name not in included_columns:
            continue
        if classify_column(column_name) == "metadata":
            continue
        question_columns[column_name] = QuestionColumnSchema(
            column_role="question",
            question_type=declared_type,
            include_in_analysis=column_name in included_columns,
        )

    stored_path = store_uploaded_dataset(
        source_path=csv_path,
        filename=csv_path.name,
        project_slug=project_slug,
        workspace_root=workspace_root,
    )

    dataset_id = str(uuid4())
    analysis_run_id = str(uuid4())
    schema_payload = {key: value.model_dump() for key, value in question_columns.items()}
    overrides_payload = {
        column_name: {
            "question_type": column_types[index],
            "include_in_analysis": column_name in included_columns,
        }
        for index, column_name in enumerate(column_titles)
        if index < len(column_types)
    }

    schema_dir = workspace_root / "projects" / project_slug / "data" / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    schema_path = schema_dir / f"{dataset_id}.json"
    schema_path.write_text(
        json.dumps(schema_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    engine = get_engine(workspace_root)
    with Session(engine) as session:
        record = DatasetRecord(
            dataset_id=dataset_id,
            project_slug=project_slug,
            source_path=str(stored_path),
            dataset_schema=schema_payload,
            analysis_run_id=analysis_run_id,
            format_type=detection.format_type,
            column_overrides_json=overrides_payload,
        )
        session.add(record)
        session.add(
            AnalysisRunRecord(
                analysis_run_id=analysis_run_id,
                project_slug=project_slug,
                wave_id=current_wave.id if current_wave is not None else None,
                dataset_id=dataset_id,
                status="ready",
            )
        )
        session.commit()

    return ImportedDataset(
        dataset_id=dataset_id,
        project_slug=project_slug,
        source_path=str(stored_path),
        question_columns=question_columns,
        analysis_run_id=analysis_run_id,
    )


def store_uploaded_dataset(
    *,
    source_path: Path,
    filename: str,
    project_slug: str,
    workspace_root: Path,
) -> Path:
    raw_dir = workspace_root / "projects" / project_slug / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target_path = raw_dir / filename
    if target_path.exists():
        target_path = raw_dir / f"{source_path.stem}-{uuid4().hex[:8]}{source_path.suffix}"
    shutil.copy2(source_path, target_path)
    return target_path
