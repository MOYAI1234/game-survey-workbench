"""Insight re-generation with adjusted parameters."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from game_survey_workbench.app import create_app
from game_survey_workbench.db import get_engine
from game_survey_workbench.llm.client import FakeLLMClient
from game_survey_workbench.models.insight import InsightRecord
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file


def test_regenerate_insights_with_different_goal(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    monkeypatch.setattr(
        FakeLLMClient,
        "generate",
        lambda self, prompt: (
            '{"themes": [{"theme_name": "Pricing", "count": 1, '
            '"example_responses": ["too expensive"]}], "uncoded_count": 0}'
            if "Open Text Coding Prompt" in prompt
            else (
                "Monetization friction dominates feedback."
                if "monetization feedback" in prompt
                else "Overall satisfaction is mixed."
            )
        ),
    )

    source = tmp_path / "monetization.md"
    source.write_text(
        "---\n"
        "title: Monetization Guide\n"
        "doc_type: guide\n"
        "stage:\n"
        "  - analysis\n"
        "scenario: monetization\n"
        "---\n"
        "Track how pricing friction changes perceived value.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(source, project_root=tmp_path)

    with TestClient(create_app()) as client:
        client.post(
            "/projects",
            json={
                "slug": "iter-proj",
                "name": "Iter",
                "knowledge_pack": {
                    "doc_types": ["guide"],
                    "scenarios": ["monetization"],
                },
            },
        )
        response = client.post(
            "/projects/iter-proj/datasets/import",
            files={
                "file": (
                    "data.csv",
                    (
                        "Q1,Q2\n"
                        "single_choice,free_text\n"
                        "Other,great game\n"
                        "Other,too expensive\n"
                    ).encode(),
                    "text/csv",
                )
            },
        )
        run_id = response.json()["analysis_run_id"]

        client.post(
            f"/projects/iter-proj/analysis/{run_id}/code-text-all",
            follow_redirects=False,
        )

        resp1 = client.post(
            f"/projects/iter-proj/analysis/{run_id}/insights-generate",
            data={"research_goal": "overall satisfaction"},
            follow_redirects=False,
        )
        resp2 = client.post(
            f"/projects/iter-proj/analysis/{run_id}/insights-generate",
            data={"research_goal": "monetization feedback"},
            follow_redirects=False,
        )

        analysis_page = client.get(f"/projects/iter-proj/analysis/{run_id}")

    engine = get_engine(tmp_path)
    with Session(engine) as session:
        insights = list(
            session.exec(
                select(InsightRecord).where(InsightRecord.analysis_run_id == run_id)
            ).all()
        )

    assert resp1.status_code == 303
    assert resp2.status_code == 303
    assert len(insights) == 2
    assert "insights-generate" in analysis_page.text
    assert "Monetization friction dominates feedback." in analysis_page.text
