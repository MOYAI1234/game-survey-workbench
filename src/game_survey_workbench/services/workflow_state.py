"""Workflow state machine for analysis runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import get_engine
from game_survey_workbench.models.analysis_run import AnalysisRunRecord


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
