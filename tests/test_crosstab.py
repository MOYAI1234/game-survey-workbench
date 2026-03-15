from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.models.crosstab import CrosstabResult
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.analysis_context import build_crosstab_findings_for_run
from game_survey_workbench.services.crosstab import compute_crosstab, describe_crosstab
from game_survey_workbench.services.dataset_import import import_dataset
from game_survey_workbench.services.projects import create_project


def test_crosstab_single_choice_by_single_choice():
    df = pd.DataFrame(
        {
            "Q1_Satisfaction": [
                "Very Satisfied",
                "Dissatisfied",
                "Very Satisfied",
                "Neutral",
                "Dissatisfied",
            ],
            "Q2_PlayerType": ["Whale", "Minnow", "Whale", "Minnow", "Whale"],
        }
    )
    result = compute_crosstab(
        dataframe=df,
        row_column="Q1_Satisfaction",
        col_column="Q2_PlayerType",
    )
    assert isinstance(result, CrosstabResult)
    assert result.row_column == "Q1_Satisfaction"
    assert result.col_column == "Q2_PlayerType"
    assert "Whale" in result.col_values
    assert "Minnow" in result.col_values

    whale_dist = result.table["Whale"]
    assert whale_dist["Very Satisfied"]["count"] == 2
    assert whale_dist["Dissatisfied"]["count"] == 1

    whale_pct_sum = sum(value["percentage"] for value in whale_dist.values())
    assert abs(whale_pct_sum - 1.0) < 0.01


def test_crosstab_scale_by_single_choice():
    df = pd.DataFrame(
        {
            "Q1_Score": [5, 2, 4, 3, 1],
            "Q2_Region": ["NA", "EU", "NA", "EU", "NA"],
        }
    )
    result = compute_crosstab(
        dataframe=df,
        row_column="Q1_Score",
        col_column="Q2_Region",
        row_type="scale",
    )
    assert "NA" in result.col_values
    na_summary = result.group_summaries["NA"]
    assert "mean" in na_summary
    assert "top_box_rate" in na_summary
    assert abs(na_summary["mean"] - 3.333) < 0.01


def test_describe_crosstab_returns_readable_text():
    df = pd.DataFrame(
        {
            "Satisfaction": ["High", "Low", "High", "High"],
            "Segment": ["Payer", "Free", "Payer", "Free"],
        }
    )
    result = compute_crosstab(
        dataframe=df,
        row_column="Satisfaction",
        col_column="Segment",
    )
    text = describe_crosstab(result)
    assert "Satisfaction" in text
    assert "Segment" in text
    assert "Payer" in text


def test_crosstab_empty_column_raises():
    df = pd.DataFrame({"A": pd.Series(dtype=str), "B": pd.Series(dtype=str)})
    with pytest.raises(ValueError, match="empty"):
        compute_crosstab(dataframe=df, row_column="A", col_column="B")


def test_build_crosstab_findings_for_run_returns_segmented_summaries(tmp_path: Path):
    create_project(
        ProjectCreate(slug="demo", name="Demo", knowledge_pack={}),
        workspace_root=tmp_path,
    )
    dataset_path = tmp_path / "survey.csv"
    dataset_path.write_text(
        "Segment,Satisfaction,Score\n"
        "metadata,single_choice,scale\n"
        "Whale,High,5\n"
        "Whale,Low,2\n"
        "Minnow,High,4\n"
        "Minnow,High,3\n",
        encoding="utf-8",
    )
    imported = import_dataset(dataset_path, project_slug="demo", workspace_root=tmp_path)

    findings = build_crosstab_findings_for_run(
        analysis_run_id=imported.analysis_run_id,
        workspace_root=tmp_path,
        segment_column="Segment",
    )

    assert len(findings) == 2
    assert any("Satisfaction by Segment" in finding for finding in findings)
    assert any("Score by Segment" in finding for finding in findings)


def test_create_crosstab_route_returns_table_and_description(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))

    client = TestClient(create_app())
    client.post(
        "/projects",
        json={"slug": "demo", "name": "Demo", "knowledge_pack": {}},
    )

    response = client.post(
        "/projects/demo/datasets/import",
        files={
            "file": (
                "survey.csv",
                (
                    "Segment,Satisfaction,Score\n"
                    "metadata,single_choice,scale\n"
                    "Whale,High,5\n"
                    "Whale,Low,2\n"
                    "Minnow,High,4\n"
                    "Minnow,High,3\n"
                ),
                "text/csv",
            )
        },
    )
    analysis_run_id = response.json()["analysis_run_id"]

    crosstab_response = client.post(
        "/crosstabs",
        json={
            "analysis_run_id": analysis_run_id,
            "row_column": "Satisfaction",
            "col_column": "Segment",
        },
    )

    assert crosstab_response.status_code == 200
    payload = crosstab_response.json()
    assert payload["row_column"] == "Satisfaction"
    assert payload["col_column"] == "Segment"
    assert "Whale" in payload["table"]
    assert "Cross-tabulation: Satisfaction by Segment" in payload["description"]
