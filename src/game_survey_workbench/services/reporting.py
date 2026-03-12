from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from jinja2 import Environment, FileSystemLoader
from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.analysis_run import AnalysisRunRecord
from game_survey_workbench.models.reporting import ReportRecord


def get_environment() -> Environment:
    template_root = Path(__file__).resolve().parent.parent / "templates"
    return Environment(loader=FileSystemLoader(template_root))


def render_report_markdown(title: str, summary_points: list[str], sections: dict[str, list[str]]) -> str:
    template = get_environment().get_template("reports/report.md.j2")
    return template.render(title=title, summary_points=summary_points, sections=sections)


def get_analysis_run_record(*, analysis_run_id: str, workspace_root: Path) -> AnalysisRunRecord | None:
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        return session.exec(
            select(AnalysisRunRecord).where(AnalysisRunRecord.analysis_run_id == analysis_run_id)
        ).first()


def save_report(
    *,
    project_slug: str,
    analysis_run_id: str,
    workspace_root: Path,
    title: str,
    summary_points: list[str],
    sections: dict[str, list[str]],
) -> Path:
    create_db_and_tables(workspace_root)
    report_dir = workspace_root / "projects" / project_slug / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    report_path = report_dir / f"report-{timestamp}-{uuid4().hex[:8]}.md"
    report_path.write_text(
        render_report_markdown(title=title, summary_points=summary_points, sections=sections),
        encoding="utf-8",
    )

    engine = get_engine(workspace_root)
    with Session(engine) as session:
        session.add(
            ReportRecord(
                project_slug=project_slug,
                analysis_run_id=analysis_run_id,
                path=str(report_path),
            )
        )
        session.commit()

    return report_path
