"""Workflow state wiring for form-triggered routes."""

import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from game_survey_workbench.app import create_app
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.analysis_run import AnalysisRunRecord
from game_survey_workbench.errors import LLM_CONFIG_ERROR_MESSAGE
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)
from game_survey_workbench.services.workflow_state import get_workflow_state


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "fake")
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def client_without_llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", raising=False)
    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", raising=False)
    with TestClient(create_app()) as test_client:
        yield test_client


def _seed_project_with_analysis(client: TestClient, workspace_root: Path, *, slug: str) -> str:
    client.post(
        "/projects",
        json={
            "slug": slug,
            "name": "Workflow Test",
            "knowledge_pack": {
                "doc_types": ["guide"],
                "scenarios": ["workflow"],
            },
        },
    )

    knowledge_dir = workspace_root / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    (knowledge_dir / "guide.md").write_text(
        "---\n"
        "title: Workflow Guide\n"
        "doc_type: guide\n"
        "stage:\n"
        "  - analysis\n"
        "scenario: workflow\n"
        "priority: 1\n"
        "---\n"
        "# Workflow Guide\n"
        "Use saved findings and coding themes to synthesize insights.\n",
        encoding="utf-8",
    )
    ingest_knowledge_file(knowledge_dir / "guide.md", project_root=workspace_root)
    replace_project_knowledge_selection(
        workspace_root=workspace_root,
        project_slug=slug,
        knowledge_document_ids=[1],
    )

    csv_content = (
        "Q1_Score,Q2_Feedback\n"
        "scale,free_text\n"
        "5,Love the graphics\n"
        "3,Too many ads\n"
        "4,Good gameplay\n"
    )
    response = client.post(
        f"/projects/{slug}/datasets/import",
        files={"file": ("data.csv", csv_content.encode(), "text/csv")},
    )
    return response.json()["analysis_run_id"]


def _load_run_state(workspace_root: Path, analysis_run_id: str):
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        run = session.exec(
            select(AnalysisRunRecord).where(
                AnalysisRunRecord.analysis_run_id == analysis_run_id
            )
        ).one()
    return get_workflow_state(run.workflow_state)


def _seed_project_with_two_free_text_questions(
    client: TestClient,
    workspace_root: Path,
    *,
    slug: str,
) -> str:
    client.post(
        "/projects",
        json={
            "slug": slug,
            "name": "Workflow Test",
            "knowledge_pack": {
                "doc_types": ["guide"],
                "scenarios": ["workflow"],
            },
        },
    )

    csv_content = (
        "Q1_Feedback,Q2_Feedback\n"
        "free_text,free_text\n"
        "Love the graphics,Too many ads\n"
        "Good gameplay,Progress is slow\n"
    )
    response = client.post(
        f"/projects/{slug}/datasets/import",
        files={"file": ("data.csv", csv_content.encode(), "text/csv")},
    )
    return response.json()["analysis_run_id"]


def test_code_text_all_advances_workflow_state(client: TestClient, tmp_path: Path):
    run_id = _seed_project_with_analysis(client, tmp_path, slug="wf-code")

    response = client.post(
        f"/projects/wf-code/analysis/{run_id}/code-text-all",
        follow_redirects=False,
    )

    state = _load_run_state(tmp_path, run_id)

    assert response.status_code == 303
    assert state.current_phase == "coded"
    assert state.completed_phases == ["coding_complete"]
    assert state.last_error is None


def test_insights_and_report_forms_advance_workflow_state(client: TestClient, tmp_path: Path):
    run_id = _seed_project_with_analysis(client, tmp_path, slug="wf-full")

    client.post(
        f"/projects/wf-full/analysis/{run_id}/code-text-all",
        follow_redirects=False,
    )
    insights_response = client.post(
        f"/projects/wf-full/analysis/{run_id}/insights-generate",
        data={"research_goal": "Understand player satisfaction"},
        follow_redirects=False,
    )
    report_response = client.post(
        "/projects/wf-full/reports/generate-form",
        data={"analysis_run_id": run_id},
        follow_redirects=False,
    )

    state = _load_run_state(tmp_path, run_id)

    assert insights_response.status_code == 303
    assert report_response.status_code == 303
    assert state.current_phase == "report_generated"
    assert state.completed_phases == [
        "coding_complete",
        "insights_complete",
        "report_complete",
    ]
    assert state.last_error is None


def test_code_text_all_records_workflow_error_on_failure(
    client_without_llm: TestClient,
    tmp_path: Path,
):
    run_id = _seed_project_with_analysis(client_without_llm, tmp_path, slug="wf-error")

    response = client_without_llm.post(
        f"/projects/wf-error/analysis/{run_id}/code-text-all",
        follow_redirects=False,
    )

    state = _load_run_state(tmp_path, run_id)

    assert response.status_code == 303
    assert state.current_phase == "imported"
    assert state.last_error == LLM_CONFIG_ERROR_MESSAGE


def test_code_text_all_runs_free_text_questions_serially_by_default(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from game_survey_workbench.routes import text_coding as text_coding_module

    run_id = _seed_project_with_two_free_text_questions(
        client,
        tmp_path,
        slug="wf-serial",
    )

    counters = {"active": 0, "max_active": 0}
    lock = threading.Lock()

    def _enter_and_sleep() -> None:
        with lock:
            counters["active"] += 1
            counters["max_active"] = max(counters["max_active"], counters["active"])
        time.sleep(0.1)
        with lock:
            counters["active"] -= 1

    def fake_code_open_text_column(*, question_column: str, **kwargs):
        _enter_and_sleep()
        return SimpleNamespace(
            question_column=question_column,
            themes=[],
            uncoded_count=0,
            citations=[],
        )

    def fake_code_open_text_column_with_status(*, question_column: str, **kwargs):
        _enter_and_sleep()
        return (
            SimpleNamespace(
                question_column=question_column,
                themes=[],
                uncoded_count=0,
                citations=[],
            ),
            "done",
        )

    monkeypatch.setattr(text_coding_module, "build_text_coding_client", lambda settings: object())
    monkeypatch.setattr(
        text_coding_module,
        "code_open_text_column",
        fake_code_open_text_column,
        raising=False,
    )
    monkeypatch.setattr(
        text_coding_module,
        "code_open_text_column_with_status",
        fake_code_open_text_column_with_status,
        raising=False,
    )

    response = client.post(
        f"/projects/wf-serial/analysis/{run_id}/code-text-all",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert counters["max_active"] == 1


def test_code_text_all_continues_other_questions_when_one_question_fails(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from game_survey_workbench.routes import text_coding as text_coding_module

    run_id = _seed_project_with_two_free_text_questions(
        client,
        tmp_path,
        slug="wf-partial-failure",
    )

    seen_questions: list[str] = []

    def fake_code_open_text_column(*, question_column: str, **kwargs):
        seen_questions.append(question_column)
        if question_column == "Q1_Feedback":
            raise RuntimeError("first question failed")
        return SimpleNamespace(
            question_column=question_column,
            themes=[],
            uncoded_count=0,
            citations=[],
        )

    def fake_code_open_text_column_with_status(*, question_column: str, **kwargs):
        seen_questions.append(question_column)
        if question_column == "Q1_Feedback":
            raise RuntimeError("first question failed")
        return (
            SimpleNamespace(
                question_column=question_column,
                themes=[],
                uncoded_count=0,
                citations=[],
            ),
            "done",
        )

    monkeypatch.setattr(text_coding_module, "build_text_coding_client", lambda settings: object())
    monkeypatch.setattr(
        text_coding_module,
        "code_open_text_column",
        fake_code_open_text_column,
        raising=False,
    )
    monkeypatch.setattr(
        text_coding_module,
        "code_open_text_column_with_status",
        fake_code_open_text_column_with_status,
        raising=False,
    )

    response = client.post(
        f"/projects/wf-partial-failure/analysis/{run_id}/code-text-all",
        follow_redirects=False,
    )

    state = _load_run_state(tmp_path, run_id)

    assert response.status_code == 303
    assert set(seen_questions) == {"Q1_Feedback", "Q2_Feedback"}
    assert state.current_phase == "imported"
    assert state.last_error is not None
