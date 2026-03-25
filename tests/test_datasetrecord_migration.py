import sqlite3
from pathlib import Path

from game_survey_workbench.db import create_db_and_tables
from game_survey_workbench.services.workspace import bootstrap_workspace


def test_create_db_and_tables_adds_stage7b_datasetrecord_columns(tmp_path: Path):
    bootstrap_workspace(tmp_path)
    db_path = tmp_path / "app.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE datasetrecord (
                id INTEGER PRIMARY KEY,
                dataset_id VARCHAR NOT NULL UNIQUE,
                project_slug VARCHAR NOT NULL,
                source_path VARCHAR NOT NULL,
                dataset_schema JSON,
                analysis_run_id VARCHAR,
                created_at DATETIME NOT NULL
            )
            """
        )
        connection.commit()

    create_db_and_tables(tmp_path)

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]: row[2]
            for row in connection.execute("PRAGMA table_info(datasetrecord)")
        }

    assert "format_type" in columns
    assert "column_overrides_json" in columns
