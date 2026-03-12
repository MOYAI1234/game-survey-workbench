import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Settings:
    workspace_root: Path


def get_settings() -> Settings:
    return Settings(
        workspace_root=Path(
            os.getenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", "workspace")
        )
    )
