import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.reporting import ReportRecord
from game_survey_workbench.services.research_waves import create_research_wave


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def project_with_report(client, tmp_path):
    slug = "report-view-test"
    client.post("/projects", json={"slug": slug, "name": "Report View Test"})

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    (knowledge_dir / "guide.md").write_text(
        "---\ntitle: Guide\ndoc_type: guide\nstages:\n  - analysis\nscenario: report-view-test\npriority: 1\n---\n# Guide\nContent.",
        encoding="utf-8",
    )

    csv_content = (
        "Q1_Score,Q2_Feedback\n"
        "scale,free_text\n"
        "5,Great\n3,OK\n4,Good\n"
    )
    resp = client.post(
        f"/projects/{slug}/datasets/import",
        files={"file": ("data.csv", csv_content.encode(), "text/csv")},
    )
    run_id = resp.json()["analysis_run_id"]

    client.post(f"/projects/{slug}/analysis/{run_id}/code-text-all")
    client.post(
        f"/projects/{slug}/analysis/{run_id}/insights",
        json={
            "research_goal": "Player satisfaction",
            "statistical_findings": [],
            "coded_themes": [],
        },
    )
    client.post(
        f"/projects/{slug}/reports/generate",
        json={"analysis_run_id": run_id},
    )
    return slug, run_id


def test_report_form_post_redirects(client):
    slug = "report-form-test"
    client.post("/projects", json={"slug": slug, "name": "Form Test"})
    csv_content = "Q1,Q2\nscale,free_text\n5,Good\n3,OK\n"
    resp = client.post(
        f"/projects/{slug}/datasets/import",
        files={"file": ("d.csv", csv_content.encode(), "text/csv")},
    )
    run_id = resp.json()["analysis_run_id"]

    response = client.post(
        f"/projects/{slug}/reports/generate-form",
        data={"analysis_run_id": run_id},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)


def test_report_latest_page_shows_content(client, project_with_report):
    slug, _ = project_with_report

    response = client.get(f"/projects/{slug}/reports/latest")

    assert response.status_code == 200
    html = response.text
    assert "研究报告" in html
    assert "report-content" in html or "narrative" in html.lower() or "Evidence" in html


def test_report_latest_page_is_scoped_to_current_wave(client, tmp_path):
    slug = "report-wave-test"
    client.post("/projects", json={"slug": slug, "name": "Report Wave Test"})
    wave_one = create_research_wave(
        workspace_root=tmp_path,
        project_slug=slug,
        name="1.0 版本问卷",
    )
    wave_two = create_research_wave(
        workspace_root=tmp_path,
        project_slug=slug,
        name="1.1 版本问卷",
    )

    report_dir = tmp_path / "projects" / slug / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    wave_one_path = report_dir / "wave-1.md"
    wave_one_path.write_text(
        "# Wave 1 Report\n\n## Executive Summary\n\nWave 1 Insight",
        encoding="utf-8",
    )
    wave_two_path = report_dir / "wave-2.md"
    wave_two_path.write_text(
        "# Wave 2 Report\n\n## Executive Summary\n\nWave 2 Insight",
        encoding="utf-8",
    )

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        session.add(
            ReportRecord(
                project_slug=slug,
                analysis_run_id="run-1",
                wave_id=wave_one.id,
                path=str(wave_one_path),
            )
        )
        session.add(
            ReportRecord(
                project_slug=slug,
                analysis_run_id="run-2",
                wave_id=wave_two.id,
                path=str(wave_two_path),
            )
        )
        session.commit()

    response = client.get(f"/projects/{slug}/reports/latest")

    assert "Wave 2 Insight" in response.text
    assert "Wave 1 Insight" not in response.text
