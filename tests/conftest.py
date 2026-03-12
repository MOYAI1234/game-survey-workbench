import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app
from game_survey_workbench.services.workspace import bootstrap_workspace

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def seeded_workspace(tmp_path: Path) -> Path:
    bootstrap_workspace(tmp_path)
    shutil.copytree(FIXTURES / "knowledge", tmp_path / "knowledge", dirs_exist_ok=True)
    raw_dir = tmp_path / "projects" / "demo" / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURES / "surveys" / "basic_survey.csv", raw_dir / "dataset.csv")
    return tmp_path


@pytest.fixture()
def client(seeded_workspace: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT",
        str(seeded_workspace),
    )
    with TestClient(create_app()) as test_client:
        yield test_client
