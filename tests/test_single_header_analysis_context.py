from pathlib import Path

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.analysis_context import load_analysis_run_context
from game_survey_workbench.services.dataset_import import import_dataset_with_overrides
from game_survey_workbench.services.projects import create_project


def test_load_analysis_run_context_preserves_all_rows_for_single_header_import(tmp_path: Path):
    create_project(
        ProjectCreate(slug="demo", name="Demo"),
        workspace_root=tmp_path,
    )
    csv_path = tmp_path / "single-header.csv"
    csv_path.write_text(
        "Gender,Feedback,Rating\n"
        "Male,Great game,5\n"
        "Female,Needs improvement,3\n"
        "Male,Love the graphics,4\n",
        encoding="utf-8",
    )

    imported = import_dataset_with_overrides(
        csv_path=csv_path,
        project_slug="demo",
        workspace_root=tmp_path,
        column_types=["single_choice", "free_text", "scale"],
        column_include=["Gender", "Feedback", "Rating"],
    )

    context = load_analysis_run_context(
        analysis_run_id=imported.analysis_run_id,
        workspace_root=tmp_path,
    )

    assert context.dataframe["Gender"].tolist() == ["Male", "Female", "Male"]
    assert context.dataframe["Feedback"].tolist() == [
        "Great game",
        "Needs improvement",
        "Love the graphics",
    ]
