from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pandas as pd
from sqlmodel import Session

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.dataset import (
    DatasetRecord,
    ImportedDataset,
    QuestionColumnSchema,
)
from game_survey_workbench.services.dataset_schema import classify_column
from game_survey_workbench.services.workspace import bootstrap_workspace


def detect_question_type(series: pd.Series) -> str:
    clean = series.dropna()
    numeric = pd.to_numeric(clean, errors="coerce")
    if not clean.empty and numeric.notna().all():
        return "scale"
    return "single_choice"


def detect_question_type_from_header_and_series(header: str, series: pd.Series) -> str:
    lowered = header.lower()
    if "multiple choices" in lowered:
        return "multi_select"
    if "feel free" in lowered or "suggestion" in lowered:
        return "free_text"
    return detect_question_type(series)


def _load_tabular_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError(f"Unsupported dataset format: {path.suffix}")


def import_dataset(csv_path: Path, *, project_slug: str, workspace_root: Path) -> ImportedDataset:
    bootstrap_workspace(workspace_root)
    create_db_and_tables(workspace_root)
    dataframe = _load_tabular_file(csv_path)

    question_columns: dict[str, QuestionColumnSchema] = {}
    for column in dataframe.columns:
        lowered = column.lower()
        if classify_column(column) == "metadata":
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
            question_type=detect_question_type_from_header_and_series(column, dataframe[column]),
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
        session.commit()

    return imported


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
