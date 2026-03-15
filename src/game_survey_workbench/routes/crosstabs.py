from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from game_survey_workbench.config import get_settings
from game_survey_workbench.services.analysis_context import load_analysis_run_context
from game_survey_workbench.services.crosstab import compute_crosstab, describe_crosstab

router = APIRouter()


class CrosstabRequest(BaseModel):
    analysis_run_id: str
    row_column: str
    col_column: str
    row_type: str = "categorical"


@router.post("/crosstabs")
def create_crosstab(payload: CrosstabRequest):
    settings = get_settings()
    context = load_analysis_run_context(
        analysis_run_id=payload.analysis_run_id,
        workspace_root=settings.workspace_root,
    )
    result = compute_crosstab(
        dataframe=context.dataframe,
        row_column=payload.row_column,
        col_column=payload.col_column,
        row_type=payload.row_type,
    )
    return {
        "row_column": result.row_column,
        "col_column": result.col_column,
        "table": result.table,
        "group_summaries": result.group_summaries,
        "description": describe_crosstab(result),
    }
