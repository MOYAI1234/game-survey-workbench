"""Browser workflow errors should be visible on the analysis page."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from game_survey_workbench.app import create_app
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.analysis_run import AnalysisRunRecord
from game_survey_workbench.models.text_coding import CodingResult
from game_survey_workbench.services.workflow_state import WorkflowState, advance_workflow


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    with TestClient(create_app()) as test_client:
        yield test_client


def _seed_analysis_run(client: TestClient, workspace_root: Path, *, slug: str) -> str:
    client.post("/projects", json={"slug": slug, "name": "Error Feedback"})

    csv_content = (
        "Q1_Score,Q2_Feedback\n"
        "scale,free_text\n"
        "5,Love the graphics\n"
        "3,Too many ads\n"
    )
    response = client.post(
        f"/projects/{slug}/datasets/import",
        files={"file": ("data.csv", csv_content.encode(), "text/csv")},
    )
    return response.json()["analysis_run_id"]


def test_error_message_shown_on_analysis_page(client: TestClient, tmp_path: Path):
    run_id = _seed_analysis_run(client, tmp_path, slug="err-proj")
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        run = session.exec(
            select(AnalysisRunRecord).where(
                AnalysisRunRecord.analysis_run_id == run_id
            )
        ).one()
        run.workflow_state = advance_workflow(
            WorkflowState(),
            "coding_failed",
            error="LLM provider unreachable",
        ).to_dict()
        session.add(run)
        session.commit()

    response = client.get(f"/projects/err-proj/analysis/{run_id}")

    assert response.status_code == 200
    assert "LLM provider unreachable" in response.text
    assert "数据已导入" in response.text


def test_analysis_page_shows_completed_workflow_events(client: TestClient, tmp_path: Path):
    run_id = _seed_analysis_run(client, tmp_path, slug="phase-proj")
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        run = session.exec(
            select(AnalysisRunRecord).where(
                AnalysisRunRecord.analysis_run_id == run_id
            )
        ).one()
        state = WorkflowState()
        state = advance_workflow(state, "coding_complete")
        state = advance_workflow(state, "insights_complete")
        run.workflow_state = state.to_dict()
        session.add(run)
        session.commit()

    response = client.get(f"/projects/phase-proj/analysis/{run_id}")

    assert response.status_code == 200
    assert "洞察合成" in response.text
    assert "文本编码" in response.text
    assert "报告生成" in response.text


def test_analysis_page_shows_fallback_notice_when_insights_generated_without_knowledge(
    client: TestClient,
    tmp_path: Path,
):
    run_id = _seed_analysis_run(client, tmp_path, slug="fallback-insight")
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        session.add(
            CodingResult(
                analysis_run_id=run_id,
                question_column="Q2_Feedback",
                themes=[{"theme_name": "广告干扰", "count": 1, "example_responses": ["Too many ads"]}],
                uncoded_count=0,
                citations=[],
            )
        )
        session.commit()

    response = client.post(
        f"/projects/fallback-insight/analysis/{run_id}/insights-generate",
        data={"research_goal": "Understand satisfaction drivers"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    detail_response = client.get(f"/projects/fallback-insight/analysis/{run_id}")

    assert detail_response.status_code == 200
    assert "当前还没有知识文档，已先生成基础版本" in detail_response.text


def test_analysis_page_shows_fallback_notice_when_coding_generated_without_knowledge(
    client: TestClient,
    tmp_path: Path,
):
    run_id = _seed_analysis_run(client, tmp_path, slug="fallback-coding")

    response = client.post(
        f"/projects/fallback-coding/analysis/{run_id}/code-text-all",
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    detail_response = client.get(f"/projects/fallback-coding/analysis/{run_id}")

    assert detail_response.status_code == 200
    assert "当前还没有知识文档，已先基于开放题答案生成基础编码结果" in detail_response.text
