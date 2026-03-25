from pathlib import Path

from sqlmodel import SQLModel, create_engine

from game_survey_workbench.models import knowledge as _knowledge_models
from game_survey_workbench.models import project as _project_models
from game_survey_workbench.models import project_knowledge_selection as _project_knowledge_selection_models
from game_survey_workbench.models import questionnaire as _questionnaire_models
from game_survey_workbench.models import dataset as _dataset_models
from game_survey_workbench.models import analysis_run as _analysis_run_models
from game_survey_workbench.models import analysis as _analysis_models
from game_survey_workbench.models import insight as _insight_models
from game_survey_workbench.models import research_brief as _research_brief_models
from game_survey_workbench.models import research_wave as _research_wave_models
from game_survey_workbench.models import reporting as _reporting_models
from game_survey_workbench.models import task_plan as _task_plan_models
from game_survey_workbench.models import text_coding as _text_coding_models
from game_survey_workbench.models import coding_job as _coding_job_models
from game_survey_workbench.services.workspace import bootstrap_workspace


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


def _ensure_projectrecord_language_column(engine) -> None:
    with engine.begin() as connection:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(projectrecord)")
        }
        if not columns:
            return
        if "language" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE projectrecord ADD COLUMN language VARCHAR NOT NULL DEFAULT 'zh'"
            )


def _ensure_analysisrunrecord_stage6a_columns(engine) -> None:
    with engine.begin() as connection:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(analysisrunrecord)")
        }
        if not columns:
            return

        if "workflow_state" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE analysisrunrecord ADD COLUMN workflow_state JSON DEFAULT '{}'"
            )
            connection.exec_driver_sql(
                "UPDATE analysisrunrecord SET workflow_state = '{}' WHERE workflow_state IS NULL"
            )
        if "wave_id" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE analysisrunrecord ADD COLUMN wave_id INTEGER"
            )


def _ensure_questionnairespecversion_stage7_columns(engine) -> None:
    with engine.begin() as connection:
        columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(questionnairespecversion)")
        }
        if not columns:
            return

        if "citations" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE questionnairespecversion ADD COLUMN citations JSON DEFAULT '[]'"
            )
            connection.exec_driver_sql(
                "UPDATE questionnairespecversion SET citations = '[]' WHERE citations IS NULL"
            )

        if "retrieved_snippets" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE questionnairespecversion ADD COLUMN retrieved_snippets JSON DEFAULT '[]'"
            )
            connection.exec_driver_sql(
                "UPDATE questionnairespecversion SET retrieved_snippets = '[]' WHERE retrieved_snippets IS NULL"
            )

        if "wave_id" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE questionnairespecversion ADD COLUMN wave_id INTEGER"
            )


def _ensure_knowledgedocument_source_format_column(engine) -> None:
    with engine.begin() as connection:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(knowledgedocument)")
        }
        if not columns:
            return

        if "source_format" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE knowledgedocument ADD COLUMN source_format VARCHAR"
            )


def _ensure_reportrecord_wave_column(engine) -> None:
    with engine.begin() as connection:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(reportrecord)")
        }
        if not columns:
            return

        if "wave_id" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE reportrecord ADD COLUMN wave_id INTEGER"
            )


def _ensure_knowledgedocument_index_columns(engine) -> None:
    with engine.begin() as connection:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(knowledgedocument)")
        }
        if not columns:
            return

        if "index_status" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE knowledgedocument ADD COLUMN index_status VARCHAR NOT NULL DEFAULT 'pending'"
            )
        if "index_error" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE knowledgedocument ADD COLUMN index_error VARCHAR"
            )
        if "chunk_count" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE knowledgedocument ADD COLUMN chunk_count INTEGER NOT NULL DEFAULT 0"
            )


def _ensure_datasetrecord_stage7b_columns(engine) -> None:
    with engine.begin() as connection:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(datasetrecord)")
        }
        if not columns:
            return

        if "format_type" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE datasetrecord ADD COLUMN format_type VARCHAR"
            )
        if "column_overrides_json" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE datasetrecord ADD COLUMN column_overrides_json JSON"
            )


def create_db_and_tables(workspace_root: Path) -> None:
    bootstrap_workspace(workspace_root)
    engine = get_engine(workspace_root)
    SQLModel.metadata.create_all(engine)
    _ensure_projectrecord_stage3a_columns(engine)
    _ensure_projectrecord_language_column(engine)
    _ensure_analysisrunrecord_stage6a_columns(engine)
    _ensure_questionnairespecversion_stage7_columns(engine)
    _ensure_knowledgedocument_source_format_column(engine)
    _ensure_knowledgedocument_index_columns(engine)
    _ensure_reportrecord_wave_column(engine)
    _ensure_datasetrecord_stage7b_columns(engine)
