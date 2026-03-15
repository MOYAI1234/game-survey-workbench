import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from game_survey_workbench.app import create_app
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.insight import InsightRecord
from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion
from game_survey_workbench.models.reporting import ReportRecord
from game_survey_workbench.models.text_coding import CodingResult


def test_healthcheck_returns_ok():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.fixture()
def fake_llm_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    with TestClient(create_app()) as client:
        yield client, tmp_path


def test_fake_llm_workflow_smoke(fake_llm_client):
    client, workspace_root = fake_llm_client

    create_response = client.post(
        "/projects/create",
        data={
            "slug": "smoke-proj",
            "name": "Smoke Project",
            "description": "workflow smoke",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 303

    brief_response = client.post(
        "/projects/smoke-proj/brief/save",
        data={
            "background": "想了解小游戏玩家对赛季通行证的看法。",
            "objectives": "了解满意点\n识别改进方向",
            "hypotheses": "玩家喜欢奖励但不喜欢 grind",
            "target_audience": "最近 30 天活跃玩家",
            "success_criteria": "输出可执行问卷和洞察",
        },
        follow_redirects=False,
    )
    assert brief_response.status_code == 303

    knowledge_response = client.post(
        "/projects/smoke-proj/knowledge/upload",
        data={
            "purposes": [
                "questionnaire_design",
                "questionnaire_analysis",
                "reporting",
            ]
        },
        files={
            "file": (
                "season-pass-guide.md",
                io.BytesIO(
                    "# 赛季通行证研究指南\n\n关注奖励吸引力、肝度和长期留存。".encode(
                        "utf-8"
                    )
                ),
                "text/markdown",
            )
        },
        follow_redirects=False,
    )
    assert knowledge_response.status_code == 303
    assert "upload_success=" in knowledge_response.headers["location"]

    questionnaire_response = client.post(
        "/projects/smoke-proj/questionnaires/draft-form",
        data={"research_goal": "为赛季通行证满意度研究生成英文问卷"},
        follow_redirects=False,
    )
    assert questionnaire_response.status_code == 303

    dataset_path = Path(__file__).parent / "fixtures" / "surveys" / "basic_survey.csv"
    with dataset_path.open("rb") as handle:
        dataset_response = client.post(
            "/projects/smoke-proj/datasets/import-form",
            files={"file": ("basic_survey.csv", handle, "text/csv")},
            follow_redirects=False,
        )
    assert dataset_response.status_code == 303
    assert "/projects/smoke-proj/analysis/" in dataset_response.headers["location"]

    coding_response = client.post(
        "/projects/smoke-proj/analysis/latest/code-text-all",
        follow_redirects=False,
    )
    assert coding_response.status_code == 303
    assert coding_response.headers["location"] == "/projects/smoke-proj/analysis/latest"

    insights_response = client.post(
        "/projects/smoke-proj/analysis/latest/insights-generate",
        data={"research_goal": "总结赛季通行证满意度与改进方向"},
        follow_redirects=False,
    )
    assert insights_response.status_code == 303
    assert insights_response.headers["location"] == "/projects/smoke-proj/analysis/latest"

    report_response = client.post(
        "/projects/smoke-proj/reports/generate-form",
        data={},
        follow_redirects=False,
    )
    assert report_response.status_code == 303
    assert report_response.headers["location"] == "/projects/smoke-proj/reports/latest"

    engine = get_engine(workspace_root)
    with Session(engine) as session:
        assert session.exec(select(QuestionnaireSpecVersion)).first() is not None
        assert session.exec(select(CodingResult)).first() is not None
        assert session.exec(select(InsightRecord)).first() is not None
        assert session.exec(select(ReportRecord)).first() is not None


def test_fake_llm_insights_smoke_without_text_coding(fake_llm_client):
    client, workspace_root = fake_llm_client

    create_response = client.post(
        "/projects/create",
        data={
            "slug": "closed-ended-proj",
            "name": "Closed Ended Project",
            "description": "closed-ended workflow smoke",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 303

    brief_response = client.post(
        "/projects/closed-ended-proj/brief/save",
        data={
            "background": "想了解玩家对新手引导满意度的看法。",
            "objectives": "识别满意度水平\n总结主要问题",
            "hypotheses": "单选题也能支持基础洞察",
            "target_audience": "新注册玩家",
            "success_criteria": "输出基础洞察",
        },
        follow_redirects=False,
    )
    assert brief_response.status_code == 303

    knowledge_response = client.post(
        "/projects/closed-ended-proj/knowledge/upload",
        data={"purposes": ["questionnaire_analysis"]},
        files={
            "file": (
                "onboarding-analysis.md",
                io.BytesIO(
                    "# 新手引导分析笔记\n\n关注流失节点、满意度分布与改进建议。".encode(
                        "utf-8"
                    )
                ),
                "text/markdown",
            )
        },
        follow_redirects=False,
    )
    assert knowledge_response.status_code == 303

    dataset_response = client.post(
        "/projects/closed-ended-proj/datasets/import-form",
        files={
            "file": (
                "closed-ended.csv",
                io.BytesIO(
                    (
                        "Q1_Segment,Q2_Satisfaction,Q3_PrimaryIssue\n"
                        "single_choice,scale,single_choice\n"
                        "New,5,Controls\n"
                        "New,4,Clarity\n"
                        "Returning,2,Pacing\n"
                    ).encode("utf-8")
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert dataset_response.status_code == 303

    insights_response = client.post(
        "/projects/closed-ended-proj/analysis/latest/insights-generate",
        data={"research_goal": "总结新手引导满意度与主要问题"},
        follow_redirects=False,
    )
    assert insights_response.status_code == 303
    assert insights_response.headers["location"] == "/projects/closed-ended-proj/analysis/latest"

    detail_response = client.get("/projects/closed-ended-proj/analysis/latest")
    assert detail_response.status_code == 200
    assert "No saved coding results found" not in detail_response.text

    engine = get_engine(workspace_root)
    with Session(engine) as session:
        insight = session.exec(
            select(InsightRecord).where(InsightRecord.analysis_run_id.is_not(None))
        ).first()

    assert insight is not None
