"""Questionnaire version history and comparison."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session

from game_survey_workbench.app import create_app
from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.questionnaire import QuestionnaireSpecVersion
from game_survey_workbench.services.questionnaire_versions import (
    diff_versions,
    list_versions,
)


def test_list_versions_returns_all(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        for i in range(3):
            session.add(
                QuestionnaireSpecVersion(
                    project_slug="proj-a",
                    version_id=f"v{i}",
                    research_goal=f"goal {i}",
                    markdown_spec=f"# Draft {i}\n\nContent version {i}",
                    citations=[],
                    retrieved_snippets=[],
                    created_at=datetime(2026, 3, 15, i, 0, 0, tzinfo=timezone.utc),
                )
            )
        session.commit()

        versions = list_versions(session, "proj-a")

    assert len(versions) == 3
    assert versions[0].version_id == "v2"


def test_diff_versions_shows_changes(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        session.add(
            QuestionnaireSpecVersion(
                project_slug="proj-b",
                version_id="v1",
                research_goal="initial goal",
                markdown_spec="# Survey\n\n1. How often do you play?\n2. What genres?",
                citations=[],
                retrieved_snippets=[],
            )
        )
        session.add(
            QuestionnaireSpecVersion(
                project_slug="proj-b",
                version_id="v2",
                research_goal="refined goal",
                markdown_spec=(
                    "# Survey\n\n1. How often do you play?\n2. What genres?\n"
                    "3. How much do you spend?"
                ),
                citations=[],
                retrieved_snippets=[],
            )
        )
        session.commit()

        diff = diff_versions(session, "proj-b", "v1", "v2")

    assert diff.added_lines > 0
    assert "How much do you spend" in diff.unified_diff


def test_history_page_lists_versions_and_diff(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        session.add(
            QuestionnaireSpecVersion(
                project_slug="proj-c",
                version_id="v1",
                research_goal="baseline",
                markdown_spec="# Survey\n\n1. What do you like most?",
                citations=[],
                retrieved_snippets=[],
            )
        )
        session.add(
            QuestionnaireSpecVersion(
                project_slug="proj-c",
                version_id="v2",
                research_goal="baseline + monetization",
                markdown_spec=(
                    "# Survey\n\n1. What do you like most?\n2. How much do you spend?"
                ),
                citations=[],
                retrieved_snippets=[],
            )
        )
        session.commit()

    with TestClient(create_app()) as client:
        response = client.get(
            "/projects/proj-c/questionnaires/history?from_version=v1&to_version=v2"
        )

    assert response.status_code == 200
    assert "v1" in response.text
    assert "v2" in response.text
    assert "How much do you spend" in response.text
