import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.services.research_waves import create_research_wave


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    return TestClient(app)


def test_layout_has_nav(client):
    response = client.get("/")

    html = response.text
    assert "<nav" in html
    assert 'href="/"' in html


def test_all_pages_inherit_layout(client, tmp_path):
    slug = "nav-test"
    client.post("/projects", json={"slug": slug, "name": "Nav Test"})
    wave = create_research_wave(
        workspace_root=tmp_path,
        project_slug=slug,
        name="1.0 版本问卷",
    )

    for path in [
        f"/projects/{slug}",
        f"/projects/{slug}/waves/{wave.id}",
        f"/projects/{slug}/questionnaires/latest",
        f"/projects/{slug}/analysis/latest",
        f"/projects/{slug}/reports/latest",
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert "<nav" in response.text, f"Missing nav on {path}"
        assert 'class="project-sidebar"' in response.text, f"Missing project sidebar on {path}"


def test_wave_workspace_shows_wave_specific_entry_links(client, tmp_path):
    slug = "nav-test"
    client.post("/projects", json={"slug": slug, "name": "Nav Test"})
    wave = create_research_wave(
        workspace_root=tmp_path,
        project_slug=slug,
        name="1.1 版本问卷",
        goal_summary="验证新版本核心体验",
    )

    response = client.get(f"/projects/{slug}/waves/{wave.id}")

    assert response.status_code == 200
    assert "1.1 版本问卷" in response.text
    assert "验证新版本核心体验" in response.text
    assert f'href="/projects/{slug}/waves/{wave.id}/questionnaires"' in response.text
    assert f'href="/projects/{slug}/waves/{wave.id}/analysis"' in response.text
    assert f'href="/projects/{slug}/waves/{wave.id}/reports"' in response.text
    assert "wave-workspace" in response.text
    assert "wave-sidebar" in response.text
