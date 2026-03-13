from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import create_db_and_tables
from game_survey_workbench.routes.datasets import router as datasets_router
from game_survey_workbench.routes.insights import router as insights_router
from game_survey_workbench.routes.projects import router as projects_router
from game_survey_workbench.routes.questionnaires import router as questionnaires_router
from game_survey_workbench.routes.reports import router as reports_router
from game_survey_workbench.routes.text_coding import router as text_coding_router
from game_survey_workbench.routes.ui import router as ui_router
from game_survey_workbench.services.workspace import bootstrap_workspace


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        bootstrap_workspace(settings.workspace_root)
        create_db_and_tables(settings.workspace_root)
        yield

    app = FastAPI(lifespan=lifespan)

    @app.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(projects_router)
    app.include_router(questionnaires_router)
    app.include_router(datasets_router)
    app.include_router(text_coding_router)
    app.include_router(insights_router)
    app.include_router(reports_router)
    app.include_router(ui_router)
    app.mount(
        "/static",
        StaticFiles(directory=str(Path(__file__).resolve().parent / "static")),
        name="static",
    )

    return app
