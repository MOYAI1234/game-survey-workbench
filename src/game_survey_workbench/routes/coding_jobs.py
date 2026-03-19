from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from game_survey_workbench.config import get_settings
from game_survey_workbench.db import get_engine
from game_survey_workbench.models.coding_job import CodingBatch, CodingJob
from game_survey_workbench.services.batched_coding import (
    create_coding_job,
    get_coding_job_status,
)

router = APIRouter()


class CreateCodingJobRequest(BaseModel):
    analysis_run_id: str
    question_column: str
    responses: list[str]
    batch_size: int = 80


@router.post(
    "/projects/{project_slug}/coding-jobs",
    status_code=status.HTTP_201_CREATED,
)
def create_job(project_slug: str, payload: CreateCodingJobRequest):
    settings = get_settings()
    job, batches = create_coding_job(
        workspace_root=settings.workspace_root,
        project_slug=project_slug,
        analysis_run_id=payload.analysis_run_id,
        question_column=payload.question_column,
        responses=payload.responses,
        batch_size=payload.batch_size,
    )
    return {
        "job_id": job.id,
        "status": job.status,
        "total_batches": len(batches),
        "total_responses": job.total_responses,
    }


@router.get("/projects/{project_slug}/coding-jobs/{job_id}/status")
def job_status(project_slug: str, job_id: int):
    settings = get_settings()
    try:
        return get_coding_job_status(
            workspace_root=settings.workspace_root,
            job_id=job_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_slug}/coding-jobs/{job_id}/cancel")
def cancel_job(project_slug: str, job_id: int):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        job = session.exec(select(CodingJob).where(CodingJob.id == job_id)).first()
        if job is None:
            raise HTTPException(status_code=404, detail="Coding job not found")
        job.status = "cancelled"
        job.finished_at = datetime.now(UTC)
        session.add(job)
        session.commit()
    return {"status": "cancelled"}


@router.post("/projects/{project_slug}/coding-jobs/{job_id}/retry-failed")
def retry_failed_batches(project_slug: str, job_id: int):
    settings = get_settings()
    engine = get_engine(settings.workspace_root)
    with Session(engine) as session:
        job = session.exec(select(CodingJob).where(CodingJob.id == job_id)).first()
        if job is None:
            raise HTTPException(status_code=404, detail="Coding job not found")
        if job.status not in ("partial", "failed"):
            raise HTTPException(status_code=400, detail="Job has no failed batches to retry")

        batches = session.exec(
            select(CodingBatch).where(
                CodingBatch.job_id == job_id,
                CodingBatch.status == "failed",
            )
        ).all()
        for batch in batches:
            batch.status = "pending"
            batch.retry_count = 0
            batch.error_message = None
            session.add(batch)
        job.status = "queued"
        job.finished_at = None
        session.add(job)
        session.commit()

    return {"status": "queued", "retried_batches": len(batches)}
