from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlmodel import Session, select

from game_survey_workbench.db import get_engine
from game_survey_workbench.errors import NoSavedCodingResultsError
from game_survey_workbench.models.analysis_run import AnalysisRunRecord, require_analysis_run
from game_survey_workbench.models.dataset import (
    DatasetRecord,
    QuestionColumnSchema,
    get_dataset_record,
)
from game_survey_workbench.models.text_coding import CodingResult
from game_survey_workbench.services.analytics import (
    describe_multi_select_summary,
    describe_scale_summary,
    describe_single_choice_summary,
)
from game_survey_workbench.services.crosstab import compute_crosstab, describe_crosstab
from game_survey_workbench.services.dataset_import import load_imported_dataset_dataframe
from game_survey_workbench.services.matrix_analytics import (
    describe_matrix_summary,
    detect_matrix_group,
    summarize_matrix_group,
)


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


def build_deterministic_findings_for_run(
    *,
    analysis_run_id: str,
    workspace_root: Path,
) -> list[str]:
    context = load_analysis_run_context(
        analysis_run_id=analysis_run_id,
        workspace_root=workspace_root,
    )
    findings: list[str] = []
    for question_column, question_payload in context.dataset_record.dataset_schema.items():
        if not isinstance(question_payload, dict):
            continue
        question_schema = QuestionColumnSchema.model_validate(question_payload)
        if not question_schema.include_in_analysis or question_column not in context.dataframe.columns:
            continue

        series = context.dataframe[question_column]
        finding: str | None = None
        if question_schema.question_type == "scale":
            finding = describe_scale_summary(question_column, series, top_box_values={4, 5})
        elif question_schema.question_type == "single_choice":
            finding = describe_single_choice_summary(question_column, series)
        elif question_schema.question_type == "multi_select":
            finding = describe_multi_select_summary(question_column, series)
        elif question_schema.question_type == "matrix":
            prefix = _derive_group_prefix(question_column)
            group_columns = detect_matrix_group(list(context.dataframe.columns), prefix=prefix)
            if group_columns and question_column == group_columns[0]:
                matrix_summary = summarize_matrix_group(
                    dataframe=context.dataframe,
                    columns=group_columns,
                    top_box_values={4, 5},
                )
                finding = describe_matrix_summary(prefix.rstrip("_"), matrix_summary)

        if finding:
            findings.append(finding)
    return findings


def _derive_group_prefix(question_column: str) -> str:
    if "_" not in question_column:
        return f"{question_column}_"
    return question_column.rsplit("_", 1)[0] + "_"


def build_crosstab_findings_for_run(
    *,
    analysis_run_id: str,
    workspace_root: Path,
    segment_column: str,
) -> list[str]:
    context = load_analysis_run_context(
        analysis_run_id=analysis_run_id,
        workspace_root=workspace_root,
    )
    if segment_column not in context.dataframe.columns:
        raise QuestionColumnNotFoundError(f"Question column '{segment_column}' not found.")

    findings: list[str] = []
    for question_column, question_payload in context.dataset_record.dataset_schema.items():
        if not isinstance(question_payload, dict):
            continue
        schema = QuestionColumnSchema.model_validate(question_payload)
        if not schema.include_in_analysis or question_column not in context.dataframe.columns:
            continue
        if schema.question_type not in ("scale", "single_choice"):
            continue
        if question_column == segment_column:
            continue

        try:
            result = compute_crosstab(
                dataframe=context.dataframe,
                row_column=question_column,
                col_column=segment_column,
                row_type=schema.question_type,
            )
        except ValueError:
            continue
        findings.append(describe_crosstab(result))
    return findings


def load_saved_coding_themes(*, analysis_run_id: str, workspace_root: Path) -> list[dict]:
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        results = list(
            session.exec(
                select(CodingResult).where(CodingResult.analysis_run_id == analysis_run_id)
            ).all()
        )

    themes = [
        {
            **theme,
            "question_column": result.question_column,
        }
        for result in results
        for theme in result.themes
        if isinstance(theme, dict)
    ]
    if not themes:
        raise NoSavedCodingResultsError("No saved coding results found for this analysis run.")
    return themes
