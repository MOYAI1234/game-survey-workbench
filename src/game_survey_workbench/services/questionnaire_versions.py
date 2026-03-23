"""Questionnaire version history and diff utilities."""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from sqlmodel import Session, select

from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion


@dataclass
class VersionDiff:
    version_a: str
    version_b: str
    added_lines: int
    removed_lines: int
    unified_diff: str


def list_versions(
    session: Session,
    project_slug: str,
    wave_id: int | None = None,
) -> list[QuestionnaireSpecVersion]:
    """Return all questionnaire versions for a project, most recent first."""
    statement = select(QuestionnaireSpecVersion).where(
        QuestionnaireSpecVersion.project_slug == project_slug
    )
    if wave_id is not None:
        statement = statement.where(QuestionnaireSpecVersion.wave_id == wave_id)
    statement = statement.order_by(QuestionnaireSpecVersion.created_at.desc())
    return list(session.exec(statement).all())


def diff_versions(
    session: Session,
    project_slug: str,
    version_id_a: str,
    version_id_b: str,
    wave_id: int | None = None,
) -> VersionDiff:
    """Compute a unified diff between two questionnaire versions."""
    statement = select(QuestionnaireSpecVersion).where(
        QuestionnaireSpecVersion.project_slug == project_slug
    )
    if wave_id is not None:
        statement = statement.where(QuestionnaireSpecVersion.wave_id == wave_id)
    versions = {
        version.version_id: version
        for version in session.exec(statement).all()
    }
    version_a = versions[version_id_a]
    version_b = versions[version_id_b]

    diff_lines = list(
        difflib.unified_diff(
            version_a.markdown_spec.splitlines(),
            version_b.markdown_spec.splitlines(),
            fromfile=version_id_a,
            tofile=version_id_b,
            lineterm="",
        )
    )
    added_lines = sum(
        1
        for line in diff_lines
        if line.startswith("+") and not line.startswith("+++")
    )
    removed_lines = sum(
        1
        for line in diff_lines
        if line.startswith("-") and not line.startswith("---")
    )
    return VersionDiff(
        version_a=version_id_a,
        version_b=version_id_b,
        added_lines=added_lines,
        removed_lines=removed_lines,
        unified_diff="\n".join(diff_lines),
    )
