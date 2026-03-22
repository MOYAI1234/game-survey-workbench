"""Workflow state machine for analysis runs."""

from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.models.analysis_run import AnalysisRunRecord
from game_survey_workbench.models.reporting import ReportRecord
from game_survey_workbench.services.workflow_state import (
    WorkflowState,
    advance_workflow,
    build_wave_progress,
    get_workflow_state,
    record_workflow_event,
)
from game_survey_workbench.services.projects import create_project
from game_survey_workbench.services.questionnaires import save_questionnaire_draft
from game_survey_workbench.models.questionnaire import QuestionnaireDraftRequest
from game_survey_workbench.services.research_waves import create_research_wave
from game_survey_workbench.services.dataset_import import import_dataset


def test_initial_state_is_imported():
    state = WorkflowState()

    assert state.current_phase == "imported"
    assert state.completed_phases == []


def test_advance_after_coding():
    state = WorkflowState()

    state = advance_workflow(state, "coding_complete")

    assert state.current_phase == "coded"
    assert "coding_complete" in state.completed_phases


def test_advance_after_insights():
    state = WorkflowState(
        current_phase="coded",
        completed_phases=["coding_complete"],
    )

    state = advance_workflow(state, "insights_complete")

    assert state.current_phase == "insights_ready"
    assert "insights_complete" in state.completed_phases


def test_advance_after_report():
    state = WorkflowState(
        current_phase="insights_ready",
        completed_phases=["coding_complete", "insights_complete"],
    )

    state = advance_workflow(state, "report_complete")

    assert state.current_phase == "report_generated"


def test_record_failure():
    state = WorkflowState()

    state = advance_workflow(state, "coding_failed", error="LLM timeout")

    assert state.current_phase == "imported"
    assert state.last_error == "LLM timeout"


def test_re_run_clears_error():
    state = WorkflowState(current_phase="imported", last_error="previous failure")

    state = advance_workflow(state, "coding_complete")

    assert state.last_error is None


def test_serialize_roundtrip():
    state = WorkflowState(
        current_phase="coded",
        completed_phases=["coding_complete"],
        last_error=None,
    )

    restored = WorkflowState.from_dict(state.to_dict())

    assert restored.current_phase == state.current_phase
    assert restored.completed_phases == state.completed_phases
    assert restored.last_error == state.last_error


def test_workflow_state_persists_on_analysis_run(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    run = AnalysisRunRecord(
        analysis_run_id="run-wf-1",
        project_slug="proj",
        dataset_id="ds-1",
    )
    state = advance_workflow(WorkflowState(), "coding_complete")
    run.workflow_state = state.to_dict()

    with Session(engine) as session:
        session.add(run)
        session.commit()
        saved = session.exec(
            select(AnalysisRunRecord).where(
                AnalysisRunRecord.analysis_run_id == "run-wf-1"
            )
        ).one()

    loaded = get_workflow_state(saved.workflow_state)

    assert loaded.current_phase == "coded"
    assert loaded.completed_phases == ["coding_complete"]


def test_build_wave_progress_reflects_current_wave_artifacts(tmp_path: Path):
    create_project(
        ProjectCreate(slug="proj", name="Project"),
        workspace_root=tmp_path,
    )
    wave = create_research_wave(
        workspace_root=tmp_path,
        project_slug="proj",
        name="1.1 版本问卷",
    )
    save_questionnaire_draft(
        project_slug="proj",
        project_name="Project",
        payload=QuestionnaireDraftRequest(research_goal="Track onboarding"),
        workspace_root=tmp_path,
        wave_id=wave.id,
        markdown_spec="# Draft",
    )
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "Q1,Q2\nsingle_choice,free_text\n满意,很好\n",
        encoding="utf-8",
    )
    dataset = import_dataset(csv_path, project_slug="proj", workspace_root=tmp_path)
    record_workflow_event(
        workspace_root=tmp_path,
        analysis_run_id=dataset.analysis_run_id,
        event="coding_complete",
    )
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    report_path = tmp_path / "projects" / "proj" / "reports" / "wave-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("# Report", encoding="utf-8")
    with Session(engine) as session:
        session.add(
            ReportRecord(
                project_slug="proj",
                analysis_run_id=dataset.analysis_run_id,
                wave_id=wave.id,
                path=str(report_path),
            )
        )
        session.commit()

    progress = build_wave_progress(
        workspace_root=tmp_path,
        project_slug="proj",
        wave_id=wave.id,
    )

    status_by_key = {item.key: item.status for item in progress}

    assert status_by_key["questionnaire_draft"] == "done"
    assert status_by_key["dataset_imported"] == "done"
    assert status_by_key["coding_complete"] == "done"
    assert status_by_key["report_generated"] == "done"
