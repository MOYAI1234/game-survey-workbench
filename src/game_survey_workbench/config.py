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
    text_coding_model: str | None = None
    text_coding_timeout_seconds: float = 90.0
    text_coding_request_mode: str = "chat_completions"
    text_coding_max_workers: int = 1
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
    text_coding_timeout = os.getenv("GAME_SURVEY_WORKBENCH_TEXT_CODING_TIMEOUT_SECONDS")
    text_coding_max_workers = os.getenv("GAME_SURVEY_WORKBENCH_TEXT_CODING_MAX_WORKERS")
    return Settings(
        workspace_root=workspace_root,
        llm_provider=os.getenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER"),
        llm_model=os.getenv("GAME_SURVEY_WORKBENCH_LLM_MODEL"),
        llm_api_key=os.getenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY"),
        llm_base_url=os.getenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL"),
        text_coding_model=os.getenv("GAME_SURVEY_WORKBENCH_TEXT_CODING_MODEL"),
        text_coding_timeout_seconds=float(text_coding_timeout) if text_coding_timeout else 90.0,
        text_coding_request_mode=os.getenv(
            "GAME_SURVEY_WORKBENCH_TEXT_CODING_REQUEST_MODE",
            "chat_completions",
        ),
        text_coding_max_workers=int(text_coding_max_workers) if text_coding_max_workers else 1,
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
