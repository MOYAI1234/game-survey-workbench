from pathlib import Path

import pandas as pd

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.analysis_context import build_deterministic_findings_for_run
from game_survey_workbench.services.dataset_import import import_dataset
from game_survey_workbench.services.matrix_analytics import (
    describe_matrix_summary,
    detect_matrix_group,
    summarize_matrix_group,
)
from game_survey_workbench.services.projects import create_project


def test_detect_matrix_group_by_prefix():
    columns = [
        "Q5_画面表现",
        "Q5_音效表现",
        "Q5_操作手感",
        "Q6_整体满意度",
    ]
    groups = detect_matrix_group(columns, prefix="Q5_")
    assert len(groups) == 3
    assert "Q5_画面表现" in groups
    assert "Q5_音效表现" in groups
    assert "Q5_操作手感" in groups


def test_summarize_matrix_group():
    df = pd.DataFrame(
        {
            "Q5_Graphics": [5, 4, 3, 5, 4],
            "Q5_Sound": [3, 2, 4, 3, 2],
            "Q5_Controls": [5, 5, 5, 4, 5],
        }
    )
    matrix_cols = ["Q5_Graphics", "Q5_Sound", "Q5_Controls"]
    summary = summarize_matrix_group(
        dataframe=df,
        columns=matrix_cols,
        top_box_values={4, 5},
    )
    assert len(summary) == 3
    controls = summary["Q5_Controls"]
    assert controls["mean"] >= 4.5
    assert controls["top_box_rate"] == 1.0

    sound = summary["Q5_Sound"]
    assert sound["mean"] < controls["mean"]


def test_describe_matrix_summary():
    df = pd.DataFrame(
        {
            "Q5_A": [5, 4, 5],
            "Q5_B": [2, 3, 2],
        }
    )
    summary = summarize_matrix_group(
        dataframe=df,
        columns=["Q5_A", "Q5_B"],
        top_box_values={4, 5},
    )
    text = describe_matrix_summary("Q5 Satisfaction Battery", summary)
    assert "Q5_A" in text
    assert "Q5_B" in text
    assert "mean" in text.lower()


def test_matrix_type_in_upload_contract():
    from game_survey_workbench.services.upload_contract import ALLOWED_TYPE_MARKERS

    assert "matrix" in ALLOWED_TYPE_MARKERS


def test_build_deterministic_findings_summarizes_matrix_group_once(tmp_path: Path):
    create_project(
        ProjectCreate(slug="demo", name="Demo", knowledge_pack={}),
        workspace_root=tmp_path,
    )
    dataset_path = tmp_path / "survey.csv"
    dataset_path.write_text(
        "Q5_Graphics,Q5_Sound,Q5_Controls\n"
        "matrix,matrix,matrix\n"
        "5,3,5\n"
        "4,2,5\n"
        "3,4,5\n",
        encoding="utf-8",
    )
    imported = import_dataset(dataset_path, project_slug="demo", workspace_root=tmp_path)

    findings = build_deterministic_findings_for_run(
        analysis_run_id=imported.analysis_run_id,
        workspace_root=tmp_path,
    )

    assert len(findings) == 1
    assert "Matrix battery" in findings[0]
    assert "Q5_Controls" in findings[0]
