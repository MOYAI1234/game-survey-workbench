from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.project import ProjectCreate, ProjectRecord
from game_survey_workbench.services.projects import create_project, get_project


def test_project_record_has_language_field_defaulting_to_zh(tmp_path: Path):
    create_db_and_tables(tmp_path)
    create_project(
        ProjectCreate(slug="demo", name="Demo"),
        workspace_root=tmp_path,
    )
    project = get_project(workspace_root=tmp_path, project_slug="demo")
    assert project is not None
    assert project.language == "zh"


def test_project_record_stores_custom_language(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)
    with Session(engine) as session:
        record = ProjectRecord(slug="en-proj", name="English Project", language="en")
        session.add(record)
        session.commit()

    project = get_project(workspace_root=tmp_path, project_slug="en-proj")
    assert project is not None
    assert project.language == "en"


def test_migration_backfills_language_for_existing_tables(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        record = ProjectRecord(slug="old", name="Old Project")
        session.add(record)
        session.commit()

    create_db_and_tables(tmp_path)

    with Session(engine) as session:
        row = session.exec(
            select(ProjectRecord).where(ProjectRecord.slug == "old")
        ).first()
        assert row is not None
        assert row.language == "zh"
