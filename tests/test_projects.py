from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.research_waves import (
    create_research_wave,
    get_current_research_wave,
    list_research_waves,
)


def test_create_project_persists_selected_knowledge_filters():
    client = TestClient(create_app())

    response = client.post(
        "/projects",
        json={
            "slug": "new-player-onboarding",
            "name": "New Player Onboarding",
            "knowledge_pack": {
                "doc_types": ["theory", "industry"],
                "scenarios": ["onboarding"],
            },
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["slug"] == "new-player-onboarding"
    assert payload["knowledge_pack"]["scenarios"] == ["onboarding"]


def test_create_research_wave_marks_newest_wave_as_current(tmp_path):
    create_project(
        ProjectCreate(slug="demo", name="Demo Project"),
        workspace_root=tmp_path,
    )

    create_research_wave(
        workspace_root=tmp_path,
        project_slug="demo",
        name="1.0 版本问卷",
    )
    second = create_research_wave(
        workspace_root=tmp_path,
        project_slug="demo",
        name="1.1 版本问卷",
    )
    current = get_current_research_wave(
        workspace_root=tmp_path,
        project_slug="demo",
    )
    waves = list_research_waves(
        workspace_root=tmp_path,
        project_slug="demo",
    )

    assert len(waves) == 2
    assert sum(1 for wave in waves if wave.is_current) == 1
    assert second.is_current is True
    assert current is not None
    assert current.id == second.id
