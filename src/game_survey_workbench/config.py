import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    workspace_root: Path
    llm_provider: str | None
    llm_model: str | None
    llm_api_key: str | None
    llm_base_url: str | None
    embedding_api_key: str | None = None
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int | None = None
    relevance_threshold: float = 1.2
    chroma_path: Path | None = None
    legacy_chunks_path: Path | None = None

    def __post_init__(self) -> None:
        self.workspace_root = Path(self.workspace_root)
        if self.chroma_path is None:
            self.chroma_path = self.workspace_root / "artifacts" / "chroma_db"
        if self.legacy_chunks_path is None:
            self.legacy_chunks_path = (
                self.workspace_root / "artifacts" / "vector_store" / "chunks.json"
            )


def get_settings() -> Settings:
    workspace_root = Path(
        os.getenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", "workspace")
    )
    embedding_dimensions = os.getenv("GAME_SURVEY_WORKBENCH_EMBEDDING_DIMENSIONS")
    return Settings(
        workspace_root=workspace_root,
        llm_provider=os.getenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER"),
        llm_model=os.getenv("GAME_SURVEY_WORKBENCH_LLM_MODEL"),
        llm_api_key=os.getenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY"),
        llm_base_url=os.getenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL"),
        embedding_api_key=os.getenv("GAME_SURVEY_WORKBENCH_EMBEDDING_API_KEY"),
        embedding_base_url=os.getenv(
            "GAME_SURVEY_WORKBENCH_EMBEDDING_BASE_URL",
            "https://api.openai.com/v1",
        ),
        embedding_model=os.getenv(
            "GAME_SURVEY_WORKBENCH_EMBEDDING_MODEL",
            "text-embedding-3-small",
        ),
        embedding_dimensions=int(embedding_dimensions) if embedding_dimensions else None,
        relevance_threshold=float(
            os.getenv("GAME_SURVEY_WORKBENCH_RELEVANCE_THRESHOLD", "1.2")
        ),
        chroma_path=workspace_root / "artifacts" / "chroma_db",
        legacy_chunks_path=workspace_root / "artifacts" / "vector_store" / "chunks.json",
    )
