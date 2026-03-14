from pathlib import Path

from fastapi.testclient import TestClient

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.research_brief import ResearchBriefPayload
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.research_brief import (
    get_research_brief,
    save_research_brief,
)


def _setup_project(tmp_path: Path) -> str:
    create_project(
        ProjectCreate(slug="bp-study", name="Battle Pass Study"),
        workspace_root=tmp_path,
    )
    return "bp-study"


def test_save_and_retrieve_brief(tmp_path: Path):
    slug = _setup_project(tmp_path)
    payload = ResearchBriefPayload(
        background="Season pass conversion dropped 12% MoM.",
        objectives=[
            "Identify friction points in pass purchase flow",
            "Measure perceived value of pass rewards",
        ],
        hypotheses=[
            "Players find the reward preview unclear",
            "Price anchor is missing after tutorial",
        ],
        target_audience="Active players L7 >= 3 days, non-payers",
        success_criteria="Actionable redesign brief for product team",
    )

    brief = save_research_brief(
        project_slug=slug,
        payload=payload,
        workspace_root=tmp_path,
    )

    assert brief.project_slug == slug
    assert brief.background == payload.background
    assert len(brief.objectives) == 2

    loaded = get_research_brief(project_slug=slug, workspace_root=tmp_path)
    assert loaded is not None
    assert loaded.id == brief.id


def test_save_brief_overwrites_previous(tmp_path: Path):
    slug = _setup_project(tmp_path)
    v1 = ResearchBriefPayload(
        background="V1 background",
        objectives=["obj1"],
    )
    save_research_brief(project_slug=slug, payload=v1, workspace_root=tmp_path)

    v2 = ResearchBriefPayload(
        background="V2 background",
        objectives=["obj1", "obj2"],
    )
    save_research_brief(project_slug=slug, payload=v2, workspace_root=tmp_path)

    loaded = get_research_brief(project_slug=slug, workspace_root=tmp_path)
    assert loaded is not None
    assert loaded.background == "V2 background"
    assert len(loaded.objectives) == 2


def test_get_brief_returns_none_when_missing(tmp_path: Path):
    slug = _setup_project(tmp_path)

    assert get_research_brief(project_slug=slug, workspace_root=tmp_path) is None


def test_put_brief_route_persists_payload(client: TestClient):
    client.post("/projects", json={"slug": "bp-study", "name": "Battle Pass Study"})

    response = client.put(
        "/projects/bp-study/brief",
        json={
            "background": "Season pass conversion dropped 12% MoM.",
            "objectives": ["Identify friction points in pass purchase flow"],
            "hypotheses": ["Players find the reward preview unclear"],
            "target_audience": "Active players L7 >= 3 days, non-payers",
            "success_criteria": "Actionable redesign brief for product team",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_slug"] == "bp-study"
    assert payload["background"] == "Season pass conversion dropped 12% MoM."


def test_get_brief_route_returns_saved_payload(client: TestClient):
    client.post("/projects", json={"slug": "bp-study", "name": "Battle Pass Study"})
    client.put(
        "/projects/bp-study/brief",
        json={
            "background": "V2 background",
            "objectives": ["obj1", "obj2"],
            "hypotheses": [],
            "target_audience": "",
            "success_criteria": "",
        },
    )

    response = client.get("/projects/bp-study/brief")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_slug"] == "bp-study"
    assert payload["background"] == "V2 background"
    assert payload["objectives"] == ["obj1", "obj2"]
