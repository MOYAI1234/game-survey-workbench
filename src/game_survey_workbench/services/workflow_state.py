"""Workflow state machine for analysis runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.analysis_run import AnalysisRunRecord
from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion
from game_survey_workbench.models.reporting import ReportRecord


_TRANSITIONS: dict[str, tuple[str, str]] = {
    "coding_complete": ("imported", "coded"),
    "insights_complete": ("coded", "insights_ready"),
    "report_complete": ("insights_ready", "report_generated"),
}

_FAILURE_EVENTS = {"coding_failed", "insights_failed", "report_failed"}


@dataclass
class WorkflowState:
    current_phase: str = "imported"
    completed_phases: list[str] = field(default_factory=list)
    last_error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "current_phase": self.current_phase,
            "completed_phases": list(self.completed_phases),
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> "WorkflowState":
        if not data:
            return cls()
        return cls(
            current_phase=str(data.get("current_phase", "imported")),
            completed_phases=list(data.get("completed_phases", [])),
            last_error=data.get("last_error"),
        )


@dataclass
class WaveProgressItem:
    key: str
    label: str
    status: str


def get_workflow_state(workflow_json: dict[str, object] | None) -> WorkflowState:
    """Load persisted workflow state, defaulting to the initial phase."""
    return WorkflowState.from_dict(workflow_json)


def advance_workflow(
    state: WorkflowState,
    event: str,
    *,
    error: str | None = None,
) -> WorkflowState:
    """Apply a workflow event and return the resulting state."""
    if event in _FAILURE_EVENTS:
        return WorkflowState(
            current_phase=state.current_phase,
            completed_phases=list(state.completed_phases),
            last_error=error,
        )

    transition = _TRANSITIONS.get(event)
    if transition is None:
        return WorkflowState(
            current_phase=state.current_phase,
            completed_phases=list(state.completed_phases),
            last_error=state.last_error,
        )

    required_phase, next_phase = transition
    if state.current_phase != required_phase:
        return WorkflowState(
            current_phase=state.current_phase,
            completed_phases=list(state.completed_phases),
            last_error=state.last_error,
        )

    completed_phases = list(state.completed_phases)
    if event not in completed_phases:
        completed_phases.append(event)

    return WorkflowState(
        current_phase=next_phase,
        completed_phases=completed_phases,
        last_error=None,
    )


def record_workflow_event(
    *,
    workspace_root: Path,
    analysis_run_id: str,
    event: str,
    error: str | None = None,
) -> WorkflowState | None:
    """Persist a workflow event on an analysis run and return the updated state."""
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        run = session.exec(
            select(AnalysisRunRecord).where(
                AnalysisRunRecord.analysis_run_id == analysis_run_id
            )
        ).first()
        if run is None:
            return None

        state = advance_workflow(
            get_workflow_state(run.workflow_state),
            event,
            error=error,
        )
        run.workflow_state = state.to_dict()
        session.add(run)
        session.commit()
        session.refresh(run)
        return state


def build_wave_progress(
    *,
    workspace_root: Path,
    project_slug: str,
    wave_id: int,
) -> list[WaveProgressItem]:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        has_questionnaire = session.exec(
            select(QuestionnaireSpecVersion.id).where(
                QuestionnaireSpecVersion.project_slug == project_slug,
                QuestionnaireSpecVersion.wave_id == wave_id,
            )
        ).first() is not None
        runs = list(
            session.exec(
                select(AnalysisRunRecord).where(
                    AnalysisRunRecord.project_slug == project_slug,
                    AnalysisRunRecord.wave_id == wave_id,
                )
            ).all()
        )
        has_report = session.exec(
            select(ReportRecord.id).where(
                ReportRecord.project_slug == project_slug,
                ReportRecord.wave_id == wave_id,
            )
        ).first() is not None

    latest_run = sorted(runs, key=lambda item: item.created_at, reverse=True)[0] if runs else None
    workflow = get_workflow_state(latest_run.workflow_state if latest_run is not None else None)
    completed = set(workflow.completed_phases)

    return [
        WaveProgressItem(
            key="questionnaire_draft",
            label="问卷草稿",
            status="done" if has_questionnaire else "pending",
        ),
        WaveProgressItem(
            key="dataset_imported",
            label="数据导入",
            status="done" if latest_run is not None else "pending",
        ),
        WaveProgressItem(
            key="coding_complete",
            label="文本编码",
            status="done" if "coding_complete" in completed else "pending",
        ),
        WaveProgressItem(
            key="insights_complete",
            label="洞察合成",
            status="done" if "insights_complete" in completed else "pending",
        ),
        WaveProgressItem(
            key="report_generated",
            label="报告生成",
            status=(
                "done"
                if has_report or "report_complete" in completed or workflow.current_phase == "report_generated"
                else "pending"
            ),
        ),
    ]
