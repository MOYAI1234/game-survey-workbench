"""Report version history and diff utilities."""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from sqlmodel import Session, select

from game_survey_workbench.models.reporting import ReportRecord


def list_report_versions(session: Session, project_slug: str) -> list[ReportRecord]:
    """Return all report records for a project, most recent first."""

    statement = (
        select(ReportRecord)
        .where(ReportRecord.project_slug == project_slug)
        .order_by(ReportRecord.created_at.desc())
    )
    return list(session.exec(statement).all())


@dataclass
class ReportDiff:
    version_a: str
    version_b: str
    added_lines: int
    removed_lines: int
    unified_diff: str


def diff_report_content(
    content_a: str,
    content_b: str,
    label_a: str = "previous",
    label_b: str = "current",
) -> ReportDiff:
    """Compute a unified diff between two report contents."""

    diff_lines = list(
        difflib.unified_diff(
            content_a.splitlines(),
            content_b.splitlines(),
            fromfile=label_a,
            tofile=label_b,
            lineterm="",
        )
    )
    added_lines = sum(
        1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
    )
    removed_lines = sum(
        1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
    )

    return ReportDiff(
        version_a=label_a,
        version_b=label_b,
        added_lines=added_lines,
        removed_lines=removed_lines,
        unified_diff="\n".join(diff_lines),
    )
