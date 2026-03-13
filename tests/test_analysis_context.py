from pathlib import Path

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.analysis_context import (
    load_analysis_run_context,
    load_free_text_responses_for_question,
)
from game_survey_workbench.services.dataset_import import import_dataset
from game_survey_workbench.services.projects import create_project


def test_load_analysis_run_context_returns_dataset_schema_and_source_path(tmp_path: Path):
    create_project(
        ProjectCreate(slug="demo", name="Demo", knowledge_pack={}),
        workspace_root=tmp_path,
    )
    dataset_path = tmp_path / "survey.csv"
    dataset_path.write_text(
        "Q1,Q1_other,Q2\n"
        "single_choice,free_text,scale\n"
        "A,too hard,5\n",
        encoding="utf-8",
    )
    imported = import_dataset(dataset_path, project_slug="demo", workspace_root=tmp_path)

    context = load_analysis_run_context(
        analysis_run_id=imported.analysis_run_id,
        workspace_root=tmp_path,
    )

    assert context.dataset_record.dataset_id == imported.dataset_id
    assert "Q1" in context.dataset_record.dataset_schema


def test_load_free_text_responses_for_question_uses_other_text_link_when_present(tmp_path: Path):
    create_project(
        ProjectCreate(slug="demo", name="Demo", knowledge_pack={}),
        workspace_root=tmp_path,
    )
    dataset_path = tmp_path / "survey.csv"
    dataset_path.write_text(
        "Why did you leave?,Why did you leave?_other\n"
        "single_choice,free_text\n"
        "Other,too hard\n"
        "Other,got bored\n",
        encoding="utf-8",
    )
    imported = import_dataset(dataset_path, project_slug="demo", workspace_root=tmp_path)

    responses = load_free_text_responses_for_question(
        analysis_run_id=imported.analysis_run_id,
        question_column="Why did you leave?",
        workspace_root=tmp_path,
    )

    assert responses == ["too hard", "got bored"]
