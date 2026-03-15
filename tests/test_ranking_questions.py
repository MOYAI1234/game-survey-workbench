from pathlib import Path

import pandas as pd

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.analysis_context import build_deterministic_findings_for_run
from game_survey_workbench.services.dataset_import import import_dataset
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.ranking_analytics import (
    describe_ranking_summary,
    normalize_ranking_data,
    summarize_ranking,
)


def test_normalize_ranking_columns():
    df = pd.DataFrame(
        {
            "Q7_Rank1": ["Graphics", "Sound", "Graphics"],
            "Q7_Rank2": ["Sound", "Graphics", "Controls"],
            "Q7_Rank3": ["Controls", "Controls", "Sound"],
        }
    )
    normalized = normalize_ranking_data(
        dataframe=df,
        columns=["Q7_Rank1", "Q7_Rank2", "Q7_Rank3"],
    )
    assert "Graphics" in normalized
    assert "Sound" in normalized
    assert "Controls" in normalized
    assert abs(normalized["Graphics"]["avg_rank"] - 1.333) < 0.01


def test_normalize_ranking_numeric_columns():
    df = pd.DataFrame(
        {
            "Q7_Graphics": [1, 2, 1],
            "Q7_Sound": [2, 1, 3],
            "Q7_Controls": [3, 3, 2],
        }
    )
    normalized = normalize_ranking_data(
        dataframe=df,
        columns=["Q7_Graphics", "Q7_Sound", "Q7_Controls"],
        format="item_as_column",
    )
    assert "Q7_Graphics" in normalized
    assert abs(normalized["Q7_Graphics"]["avg_rank"] - 1.333) < 0.01


def test_summarize_ranking():
    df = pd.DataFrame(
        {
            "Q7_Rank1": ["A", "B", "A", "A"],
            "Q7_Rank2": ["B", "A", "B", "C"],
            "Q7_Rank3": ["C", "C", "C", "B"],
        }
    )
    summary = summarize_ranking(
        dataframe=df,
        columns=["Q7_Rank1", "Q7_Rank2", "Q7_Rank3"],
    )
    items_by_rank = sorted(summary.items(), key=lambda item: item[1]["avg_rank"])
    assert items_by_rank[0][0] == "A"


def test_describe_ranking():
    df = pd.DataFrame(
        {
            "Q7_Rank1": ["A", "B"],
            "Q7_Rank2": ["B", "A"],
        }
    )
    summary = summarize_ranking(
        dataframe=df,
        columns=["Q7_Rank1", "Q7_Rank2"],
    )
    text = describe_ranking_summary("Feature Priority", summary)
    assert "Feature Priority" in text
    assert "A" in text


def test_ranking_type_in_upload_contract():
    from game_survey_workbench.services.upload_contract import ALLOWED_TYPE_MARKERS

    assert "ranking" in ALLOWED_TYPE_MARKERS


def test_build_deterministic_findings_summarizes_ranking_group_once(tmp_path: Path):
    create_project(
        ProjectCreate(slug="demo", name="Demo", knowledge_pack={}),
        workspace_root=tmp_path,
    )
    dataset_path = tmp_path / "survey.csv"
    dataset_path.write_text(
        "Q7_Rank1,Q7_Rank2,Q7_Rank3\n"
        "ranking,ranking,ranking\n"
        "Graphics,Sound,Controls\n"
        "Sound,Graphics,Controls\n"
        "Graphics,Controls,Sound\n",
        encoding="utf-8",
    )
    imported = import_dataset(dataset_path, project_slug="demo", workspace_root=tmp_path)

    findings = build_deterministic_findings_for_run(
        analysis_run_id=imported.analysis_run_id,
        workspace_root=tmp_path,
    )

    assert len(findings) == 1
    assert "Ranking 'Q7'" in findings[0]
    assert "Graphics" in findings[0]
