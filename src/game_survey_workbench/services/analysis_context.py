from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from game_survey_workbench.models.analysis_run import AnalysisRunRecord, require_analysis_run
from game_survey_workbench.models.dataset import (
    DatasetRecord,
    QuestionColumnSchema,
    get_dataset_record,
)
from game_survey_workbench.services.dataset_import import load_imported_dataset_dataframe


class QuestionColumnNotFoundError(ValueError):
    pass


class NoFreeTextResponsesFoundError(ValueError):
    pass


@dataclass
class AnalysisRunContext:
    analysis_run: AnalysisRunRecord
    dataset_record: DatasetRecord
    dataframe: pd.DataFrame


def load_analysis_run_context(*, analysis_run_id: str, workspace_root: Path) -> AnalysisRunContext:
    analysis_run = require_analysis_run(analysis_run_id, workspace_root=workspace_root)
    dataset_record = get_dataset_record(analysis_run.dataset_id, workspace_root=workspace_root)
    if dataset_record is None:
        raise ValueError("Dataset record not found.")

    dataframe = load_imported_dataset_dataframe(Path(dataset_record.source_path))
    return AnalysisRunContext(
        analysis_run=analysis_run,
        dataset_record=dataset_record,
        dataframe=dataframe,
    )


def load_free_text_responses_for_question(
    *,
    analysis_run_id: str,
    question_column: str,
    workspace_root: Path,
) -> list[str]:
    context = load_analysis_run_context(
        analysis_run_id=analysis_run_id,
        workspace_root=workspace_root,
    )
    question_payload = context.dataset_record.dataset_schema.get(question_column)
    if not isinstance(question_payload, dict):
        raise QuestionColumnNotFoundError(f"Question column '{question_column}' not found.")

    question_schema = QuestionColumnSchema.model_validate(question_payload)
    response_column = question_schema.other_text_column or question_column
    if response_column not in context.dataframe.columns:
        raise QuestionColumnNotFoundError(f"Question column '{response_column}' not found.")

    series = context.dataframe[response_column].dropna().astype(str).str.strip()
    responses = [value for value in series.tolist() if value]
    if not responses:
        raise NoFreeTextResponsesFoundError(f"No free-text responses found for '{question_column}'.")
    return responses
