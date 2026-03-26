from __future__ import annotations

import threading
from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import get_engine
from game_survey_workbench.models.coding_job import CodingBatch, CodingJob
from game_survey_workbench.models.text_coding import CodingResult
from game_survey_workbench.services.analysis_context import load_analysis_run_context

_ACTIVE_ANALYSIS_RUNS: set[str] = set()
_ACTIVE_LOCK = threading.Lock()


def mark_analysis_run_active(analysis_run_id: str) -> bool:
    with _ACTIVE_LOCK:
        if analysis_run_id in _ACTIVE_ANALYSIS_RUNS:
            return False
        _ACTIVE_ANALYSIS_RUNS.add(analysis_run_id)
        return True


def unmark_analysis_run_active(analysis_run_id: str) -> None:
    with _ACTIVE_LOCK:
        _ACTIVE_ANALYSIS_RUNS.discard(analysis_run_id)


def is_analysis_run_active(analysis_run_id: str) -> bool:
    with _ACTIVE_LOCK:
        return analysis_run_id in _ACTIVE_ANALYSIS_RUNS


def get_coding_progress_snapshot(
    *,
    workspace_root: Path,
    analysis_run_id: str,
) -> dict[str, object]:
    loaded_context = load_analysis_run_context(
        analysis_run_id=analysis_run_id,
        workspace_root=workspace_root,
    )
    free_text_questions = [
        question_column
        for question_column, payload in loaded_context.dataset_record.dataset_schema.items()
        if isinstance(payload, dict) and payload.get("question_type") == "free_text"
    ]
    total_questions = len(free_text_questions)
    if total_questions == 0:
        return {
            "status": "idle",
            "status_text": "当前数据中没有开放题，无需文本编码。",
            "progress_percent": 100,
            "total_questions": 0,
            "completed_questions": 0,
            "total_batches": 0,
            "completed_batches": 0,
            "failed_batches": 0,
            "coded_responses": 0,
            "total_responses": 0,
            "polling": False,
        }

    engine = get_engine(workspace_root)
    with Session(engine) as session:
        jobs = list(
            session.exec(
                select(CodingJob).where(CodingJob.analysis_run_id == analysis_run_id)
            ).all()
        )
        results = list(
            session.exec(
                select(CodingResult).where(CodingResult.analysis_run_id == analysis_run_id)
            ).all()
        )

    latest_jobs_by_question: dict[str, CodingJob] = {}
    for job in sorted(jobs, key=lambda item: item.id or 0):
        latest_jobs_by_question[job.question_column] = job

    latest_jobs = [
        latest_jobs_by_question[question]
        for question in free_text_questions
        if question in latest_jobs_by_question
    ]

    job_ids = [job.id for job in latest_jobs if job.id is not None]
    batches_by_job: dict[int, list[CodingBatch]] = {job_id: [] for job_id in job_ids}
    if job_ids:
        with Session(engine) as session:
            batches = list(
                session.exec(
                    select(CodingBatch).where(CodingBatch.job_id.in_(job_ids))
                ).all()
            )
        for batch in batches:
            batches_by_job.setdefault(batch.job_id, []).append(batch)

    completed_result_questions = {
        result.question_column
        for result in results
        if result.question_column in free_text_questions
    }
    completed_job_questions = {
        job.question_column
        for job in latest_jobs
        if job.status == "done"
    }
    completed_questions = len(completed_result_questions | completed_job_questions)

    total_batches = sum(len(batches_by_job.get(job.id or -1, [])) for job in latest_jobs)
    completed_batches = sum(
        1
        for job in latest_jobs
        for batch in batches_by_job.get(job.id or -1, [])
        if batch.status == "done"
    )
    failed_batches = sum(
        1
        for job in latest_jobs
        for batch in batches_by_job.get(job.id or -1, [])
        if batch.status == "failed"
    )
    coded_responses = sum(job.coded_responses for job in latest_jobs)
    total_responses = sum(job.total_responses for job in latest_jobs)

    running_batches = [
        batch
        for job in latest_jobs
        for batch in batches_by_job.get(job.id or -1, [])
        if batch.status == "running"
    ]
    latest_retry = max((batch.retry_count for batch in running_batches), default=0)

    has_running_job = any(job.status in {"queued", "running"} for job in latest_jobs)
    has_failed_job = any(job.status in {"failed", "partial"} for job in latest_jobs)
    active = is_analysis_run_active(analysis_run_id)

    if has_running_job or active:
        status = "running"
        if latest_retry > 0:
            status_text = f"文本编码进行中，当前批次正在第 {latest_retry + 1} 次尝试。"
        elif total_batches > 0:
            status_text = (
                f"文本编码进行中，已完成 {completed_batches}/{total_batches} 个批次，"
                f"{completed_questions}/{total_questions} 道开放题已完成。"
            )
        else:
            status_text = "正在准备文本编码任务…"
    elif completed_questions >= total_questions:
        status = "complete"
        status_text = "文本编码完成。"
    elif has_failed_job:
        status = "partial" if completed_questions > 0 else "failed"
        status_text = (
            "文本编码部分完成，存在失败批次。"
            if completed_questions > 0
            else "文本编码失败，请重试。"
        )
    else:
        status = "idle"
        status_text = "尚未开始文本编码。"

    if total_responses > 0:
        progress_percent = int(round((coded_responses / total_responses) * 100))
    else:
        progress_percent = int(round((completed_questions / total_questions) * 100))

    return {
        "status": status,
        "status_text": status_text,
        "progress_percent": max(0, min(progress_percent, 100)),
        "total_questions": total_questions,
        "completed_questions": completed_questions,
        "total_batches": total_batches,
        "completed_batches": completed_batches,
        "failed_batches": failed_batches,
        "coded_responses": coded_responses,
        "total_responses": total_responses,
        "polling": status == "running",
    }
