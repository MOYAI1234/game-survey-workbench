from pathlib import Path

from game_survey_workbench.services.workspace import bootstrap_workspace


def test_bootstrap_workspace_creates_expected_directories(tmp_path: Path):
    bootstrap_workspace(tmp_path)

    assert (tmp_path / "knowledge").exists()
    assert (tmp_path / "projects").exists()
    assert (tmp_path / "artifacts").exists()


def test_run_bat_uses_python_module_uv_entrypoint():
    script_path = Path(__file__).resolve().parents[1] / "run.bat"
    script = script_path.read_text(encoding="utf-8")

    assert "call python -m uv sync --extra dev" in script
    assert 'set "PYTHONPATH=%CD%\\src"' in script
    assert "netstat -ano" in script
    assert "findstr :8000" in script
    assert "Port 8000 is already in use." in script
    assert (
        "call python -m uvicorn --app-dir src "
        "game_survey_workbench.app:create_app --factory "
        "--host 127.0.0.1 --port 8000"
    ) in script
    assert "--reload" not in script
