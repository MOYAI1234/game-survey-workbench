from pathlib import Path

from game_survey_workbench.services.workspace import bootstrap_workspace


def test_bootstrap_workspace_creates_expected_directories(tmp_path: Path):
    bootstrap_workspace(tmp_path)

    assert (tmp_path / "knowledge").exists()
    assert (tmp_path / "projects").exists()
    assert (tmp_path / "artifacts").exists()
