from pathlib import Path

from sqlmodel import SQLModel, create_engine

from game_survey_workbench.models import knowledge as _knowledge_models
from game_survey_workbench.models import project as _project_models
from game_survey_workbench.models import questionnaire as _questionnaire_models
from game_survey_workbench.models import dataset as _dataset_models
from game_survey_workbench.models import analysis_run as _analysis_run_models
from game_survey_workbench.models import analysis as _analysis_models
from game_survey_workbench.models import insight as _insight_models
from game_survey_workbench.models import reporting as _reporting_models
from game_survey_workbench.models import text_coding as _text_coding_models


def get_engine(workspace_root: Path):
    database_path = workspace_root / "app.db"
    return create_engine(f"sqlite:///{database_path}")


def _ensure_projectrecord_stage3a_columns(engine) -> None:
    with engine.begin() as connection:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(projectrecord)")
        }
        if not columns:
            return

        if "description" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE projectrecord ADD COLUMN description VARCHAR NOT NULL DEFAULT ''"
            )
        if "status" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE projectrecord ADD COLUMN status VARCHAR NOT NULL DEFAULT 'active'"
            )
        if "updated_at" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE projectrecord ADD COLUMN updated_at TIMESTAMP"
            )
            connection.exec_driver_sql(
                "UPDATE projectrecord SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"
            )


def create_db_and_tables(workspace_root: Path) -> None:
    engine = get_engine(workspace_root)
    SQLModel.metadata.create_all(engine)
    _ensure_projectrecord_stage3a_columns(engine)
