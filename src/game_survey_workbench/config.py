import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Settings:
    workspace_root: Path
    llm_provider: str | None
    llm_model: str | None
    llm_api_key: str | None
    llm_base_url: str | None


def get_settings() -> Settings:
    return Settings(
        workspace_root=Path(
            os.getenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", "workspace")
        ),
        llm_provider=os.getenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER"),
        llm_model=os.getenv("GAME_SURVEY_WORKBENCH_LLM_MODEL"),
        llm_api_key=os.getenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY"),
        llm_base_url=os.getenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL"),
    )
