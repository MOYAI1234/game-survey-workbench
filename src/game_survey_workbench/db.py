from pathlib import Path

from sqlmodel import SQLModel, create_engine

from game_survey_workbench.models import knowledge as _knowledge_models
from game_survey_workbench.models import project as _project_models
from game_survey_workbench.models import questionnaire as _questionnaire_models
from game_survey_workbench.models import dataset as _dataset_models
from game_survey_workbench.models import analysis_run as _analysis_run_models
from game_survey_workbench.models import analysis as _analysis_models
from game_survey_workbench.models import reporting as _reporting_models


def get_engine(workspace_root: Path):
    database_path = workspace_root / "app.db"
    return create_engine(f"sqlite:///{database_path}")


def create_db_and_tables(workspace_root: Path) -> None:
    engine = get_engine(workspace_root)
    SQLModel.metadata.create_all(engine)
