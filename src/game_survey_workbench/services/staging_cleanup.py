from __future__ import annotations

import time
from pathlib import Path


def cleanup_stale_staging_files(*, workspace_root: Path, max_age_hours: int = 24) -> int:
    cutoff = time.time() - (max_age_hours * 3600)
    removed = 0

    projects_dir = workspace_root / "projects"
    if projects_dir.exists():
        for staging_dir in projects_dir.glob("*/data/staging"):
            removed += _cleanup_dir(staging_dir, cutoff)

    knowledge_staging = workspace_root / "knowledge" / "staging"
    if knowledge_staging.exists():
        removed += _cleanup_dir(knowledge_staging, cutoff)

    return removed


def _cleanup_dir(directory: Path, cutoff: float) -> int:
    removed = 0
    for staging_file in directory.iterdir():
        if staging_file.is_file() and staging_file.stat().st_mtime < cutoff:
            staging_file.unlink()
            removed += 1
    return removed
