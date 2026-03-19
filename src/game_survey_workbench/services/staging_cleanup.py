from __future__ import annotations

import time
from pathlib import Path


def cleanup_stale_staging_files(*, workspace_root: Path, max_age_hours: int = 24) -> int:
    projects_dir = workspace_root / "projects"
    if not projects_dir.exists():
        return 0

    cutoff = time.time() - (max_age_hours * 3600)
    removed = 0

    for staging_dir in projects_dir.glob("*/data/staging"):
        for staging_file in staging_dir.iterdir():
            if staging_file.is_file() and staging_file.stat().st_mtime < cutoff:
                staging_file.unlink()
                removed += 1

    return removed
