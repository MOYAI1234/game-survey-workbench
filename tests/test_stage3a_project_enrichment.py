from pathlib import Path

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project, list_projects


def test_create_project_with_description(tmp_path: Path):
    payload = ProjectCreate(
        slug="season-pass-v2",
        name="Season Pass V2 Research",
        description="Evaluate player retention impact of the redesigned season pass.",
    )

    record = create_project(payload, workspace_root=tmp_path)

    assert record.description == payload.description
    assert record.status == "active"
    assert record.updated_at is not None


def test_list_projects_returns_all(tmp_path: Path):
    for i in range(3):
        create_project(
            ProjectCreate(slug=f"proj-{i}", name=f"Project {i}"),
            workspace_root=tmp_path,
        )

    projects = list_projects(workspace_root=tmp_path)

    assert len(projects) == 3
    slugs = [project.slug for project in projects]
    assert "proj-0" in slugs and "proj-2" in slugs


def test_project_description_defaults_to_empty(tmp_path: Path):
    payload = ProjectCreate(slug="minimal", name="Minimal")

    record = create_project(payload, workspace_root=tmp_path)

    assert record.description == ""
