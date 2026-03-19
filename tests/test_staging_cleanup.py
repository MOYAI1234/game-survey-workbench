import time
from pathlib import Path

from game_survey_workbench.services.staging_cleanup import cleanup_stale_staging_files


def test_cleanup_removes_files_older_than_threshold(tmp_path: Path):
    staging_dir = tmp_path / "projects" / "demo" / "data" / "staging"
    staging_dir.mkdir(parents=True)

    old_file = staging_dir / "old.csv"
    old_file.write_text("old data")
    old_mtime = time.time() - 90000
    old_file.touch()

    import os

    os.utime(old_file, (old_mtime, old_mtime))

    new_file = staging_dir / "new.csv"
    new_file.write_text("new data")

    removed = cleanup_stale_staging_files(workspace_root=tmp_path, max_age_hours=24)

    assert removed == 1
    assert not old_file.exists()
    assert new_file.exists()
