from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from jinja2 import Environment, FileSystemLoader
from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.analysis_run import AnalysisRunRecord
from game_survey_workbench.models.insight import InsightRecord
from game_survey_workbench.models.reporting import ReportRecord
from game_survey_workbench.models.text_coding import CodingResult


def get_environment() -> Environment:
    template_root = Path(__file__).resolve().parent.parent / "templates"
    return Environment(loader=FileSystemLoader(template_root))


def render_report_markdown(
    title: str,
    summary_points: list[str],
    sections: dict[str, list[str]],
    narrative: str | None = None,
    evidence: list[dict] | None = None,
    evidence_section: str | None = None,
) -> str:
    template = get_environment().get_template("reports/report.md.j2")
    return template.render(
        title=title,
        summary_points=summary_points,
        sections=sections,
        narrative=narrative,
        evidence=evidence or [],
        evidence_section=evidence_section,
        now=date.today().isoformat(),
    )


def get_analysis_run_record(*, analysis_run_id: str, workspace_root: Path) -> AnalysisRunRecord | None:
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        return session.exec(
            select(AnalysisRunRecord).where(AnalysisRunRecord.analysis_run_id == analysis_run_id)
        ).first()


def get_latest_insight_record(*, analysis_run_id: str, workspace_root: Path) -> InsightRecord | None:
    records = list_insight_records(
        analysis_run_id=analysis_run_id,
        workspace_root=workspace_root,
    )
    if not records:
        return None
    return records[0]


def list_insight_records(*, analysis_run_id: str, workspace_root: Path) -> list[InsightRecord]:
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        records = session.exec(
            select(InsightRecord).where(InsightRecord.analysis_run_id == analysis_run_id)
        ).all()
    return sorted(records, key=lambda item: item.created_at, reverse=True)


def get_coding_results(*, analysis_run_id: str, workspace_root: Path) -> list[CodingResult]:
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        return list(
            session.exec(
                select(CodingResult).where(CodingResult.analysis_run_id == analysis_run_id)
            ).all()
        )


def save_report(
    *,
    project_slug: str,
    analysis_run_id: str,
    workspace_root: Path,
    title: str,
    summary_points: list[str],
    sections: dict[str, list[str]],
    narrative: str | None = None,
    evidence: list[dict] | None = None,
    evidence_section: str | None = None,
) -> Path:
    create_db_and_tables(workspace_root)
    report_dir = workspace_root / "projects" / project_slug / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    report_path = report_dir / f"report-{timestamp}-{uuid4().hex[:8]}.md"
    report_path.write_text(
        render_report_markdown(
            title=title,
            summary_points=summary_points,
            sections=sections,
            narrative=narrative,
            evidence=evidence,
            evidence_section=evidence_section,
        ),
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
