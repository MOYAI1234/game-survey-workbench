from pathlib import Path
import sqlite3

from game_survey_workbench.db import create_db_and_tables
from game_survey_workbench.services.workspace import bootstrap_workspace


def test_bootstrap_workspace_creates_expected_directories(tmp_path: Path):
    bootstrap_workspace(tmp_path)

    assert (tmp_path / "knowledge").exists()
    assert (tmp_path / "projects").exists()
    assert (tmp_path / "artifacts").exists()


def test_create_db_and_tables_bootstraps_fresh_workspace(tmp_path: Path):
    workspace_root = tmp_path / "fresh-workspace"

    create_db_and_tables(workspace_root)

    assert workspace_root.exists()
    assert (workspace_root / "app.db").exists()
    assert (workspace_root / "knowledge").exists()
    assert (workspace_root / "projects").exists()
    assert (workspace_root / "artifacts").exists()


def test_create_db_and_tables_backfills_knowledge_source_format_column(tmp_path: Path):
    workspace_root = tmp_path / "legacy-workspace"
    workspace_root.mkdir()
    database_path = workspace_root / "app.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE knowledgedocument (
                id INTEGER PRIMARY KEY,
                source_path VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                doc_type VARCHAR NOT NULL DEFAULT 'experience',
                stages JSON,
                tags JSON,
                scenario VARCHAR,
                priority INTEGER NOT NULL DEFAULT 0
            )
            """
        )

    create_db_and_tables(workspace_root)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(knowledgedocument)")
        }

    assert "source_format" in columns


def test_create_db_and_tables_backfills_knowledge_index_columns(tmp_path: Path):
    workspace_root = tmp_path / "legacy-index-workspace"
    workspace_root.mkdir()
    database_path = workspace_root / "app.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE knowledgedocument (
                id INTEGER PRIMARY KEY,
                source_path VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                doc_type VARCHAR NOT NULL DEFAULT 'experience',
                stages JSON,
                tags JSON,
                scenario VARCHAR,
                priority INTEGER NOT NULL DEFAULT 0,
                source_format VARCHAR
            )
            """
        )

    create_db_and_tables(workspace_root)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(knowledgedocument)")
        }

    assert "index_status" in columns
    assert "index_error" in columns
    assert "chunk_count" in columns


def test_run_bat_uses_python_module_uv_entrypoint():
    script_path = Path(__file__).resolve().parents[1] / "run.bat"
    script = script_path.read_text(encoding="utf-8")

    assert 'set "VENV_PYTHON=%CD%\\.venv\\Scripts\\python.exe"' in script
    assert 'set "FALLBACK_VENV_PYTHON=%CD%\\..\\..\\.venv\\Scripts\\python.exe"' in script
    assert 'if not exist "%VENV_PYTHON%" set "VENV_PYTHON=%FALLBACK_VENV_PYTHON%"' in script
    assert 'if not exist "%VENV_PYTHON%" (' in script
    assert "call python -m uv sync --extra dev" in script
    assert 'set "PYTHONPATH=%CD%\\src"' in script
    assert 'set "PORT=8000"' in script
    assert 'set "PORT_CANDIDATES=8000 8014 8015 8016 8017 8018"' in script
    assert "trying the next port." in script
    assert "Could not find an available port." in script
    assert 'start "" http://127.0.0.1:!PORT!/' in script
    assert (
        'call "%VENV_PYTHON%" -m uvicorn --app-dir src '
        "game_survey_workbench.app:create_app --factory "
        "--host 127.0.0.1 --port !PORT!"
    ) in script
    assert "--reload" not in script
