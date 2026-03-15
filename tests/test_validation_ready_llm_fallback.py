from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from game_survey_workbench.app import create_app
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.analysis_run import AnalysisRunRecord


LLM_CONFIG_ERROR = "LLM 未配置，请设置环境变量后重试"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", raising=False)
    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", raising=False)
    with TestClient(create_app()) as test_client:
        yield test_client


def _create_project(client: TestClient, slug: str) -> None:
    client.post("/projects", json={"slug": slug, "name": slug})


def _import_dataset(client: TestClient, tmp_path: Path, project_slug: str) -> str:
    csv_path = tmp_path / f"{project_slug}.csv"
    csv_path.write_text(
        "segment,feedback\n"
        "metadata,free_text\n"
        "A,too many ads\n"
        "B,good core loop\n",
        encoding="utf-8",
    )
    with csv_path.open("rb") as handle:
        response = client.post(
            f"/projects/{project_slug}/datasets/import",
            files={"file": (csv_path.name, handle, "text/csv")},
        )
    return response.json()["analysis_run_id"]


def test_questionnaire_form_missing_llm_redirects_and_shows_message(
    client: TestClient,
):
    _create_project(client, "quest-proj")

    response = client.post(
        "/projects/quest-proj/questionnaires/draft-form",
        data={"research_goal": "Understand onboarding friction"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    detail_response = client.get("/projects/quest-proj/questionnaires/latest?error=llm_missing")
    assert LLM_CONFIG_ERROR in detail_response.text


def test_code_text_all_missing_llm_records_workflow_error(
    client: TestClient,
    tmp_path: Path,
):
    _create_project(client, "coding-proj")
    run_id = _import_dataset(client, tmp_path, "coding-proj")

    response = client.post(
        f"/projects/coding-proj/analysis/{run_id}/code-text-all",
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        record = session.exec(
            select(AnalysisRunRecord).where(AnalysisRunRecord.analysis_run_id == run_id)
        ).one()

    assert record.workflow_state["last_error"] == LLM_CONFIG_ERROR


def test_insights_form_missing_llm_records_error_and_analysis_page_shows_message(
    client: TestClient,
    tmp_path: Path,
):
    _create_project(client, "insight-proj")
    run_id = _import_dataset(client, tmp_path, "insight-proj")

    response = client.post(
        f"/projects/insight-proj/analysis/{run_id}/insights-generate",
        data={"research_goal": "Understand satisfaction drivers"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        record = session.exec(
            select(AnalysisRunRecord).where(AnalysisRunRecord.analysis_run_id == run_id)
        ).one()

    assert record.workflow_state["last_error"] == LLM_CONFIG_ERROR

    detail_response = client.get(f"/projects/insight-proj/analysis/{run_id}")
    assert LLM_CONFIG_ERROR in detail_response.text


def test_report_form_missing_llm_does_not_crash_when_error_is_raised(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _create_project(client, "report-proj")
    run_id = _import_dataset(client, tmp_path, "report-proj")

    from game_survey_workbench.routes import reports as reports_module
    from game_survey_workbench.llm.client import MissingLLMConfigurationError

    def _raise_missing(*args, **kwargs):
        raise MissingLLMConfigurationError("LLM runtime is not configured.")

    monkeypatch.setattr(reports_module, "generate_report", _raise_missing)

    response = client.post(
        "/projects/report-proj/reports/generate-form",
        data={"analysis_run_id": run_id},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        record = session.exec(
            select(AnalysisRunRecord).where(AnalysisRunRecord.analysis_run_id == run_id)
        ).one()

    assert record.workflow_state["last_error"] == LLM_CONFIG_ERROR
