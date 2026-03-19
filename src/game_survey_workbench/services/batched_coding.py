from __future__ import annotations

import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.llm.client import LLMClient
from game_survey_workbench.models.coding_job import CodingBatch, CodingJob
from game_survey_workbench.services.knowledge_ingest import retrieve_project_knowledge
from game_survey_workbench.services.text_coding import (
    build_coding_context,
    load_coding_prompt,
    parse_coding_response,
)

DEFAULT_BATCH_SIZE = 80
MAX_RETRIES = 2


def deduplicate_responses(responses: list[str]) -> tuple[list[str], dict[str, list[int]]]:
    seen: dict[str, list[int]] = {}
    unique: list[str] = []
    for index, text in enumerate(responses):
        stripped = text.strip()
        if not stripped:
            continue
        if stripped in seen:
            seen[stripped].append(index)
        else:
            seen[stripped] = [index]
            unique.append(stripped)
    return unique, seen


def create_coding_job(
    *,
    workspace_root: Path,
    project_slug: str,
    analysis_run_id: str,
    question_column: str,
    responses: list[str],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[CodingJob, list[CodingBatch]]:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)

    unique_responses, _mapping = deduplicate_responses(responses)
    total_batches = max(1, math.ceil(len(unique_responses) / batch_size))

    job = CodingJob(
        project_slug=project_slug,
        analysis_run_id=analysis_run_id,
        question_column=question_column,
        status="queued",
        total_responses=len(unique_responses),
        coded_responses=0,
        batch_size=batch_size,
    )

    with Session(engine) as session:
        session.add(job)
        session.commit()
        session.refresh(job)

        batches: list[CodingBatch] = []
        for batch_index in range(total_batches):
            start = batch_index * batch_size
            end = min(start + batch_size, len(unique_responses))
            batch = CodingBatch(
                job_id=job.id,
                batch_index=batch_index,
                status="pending",
                input_texts_json=unique_responses[start:end],
            )
            session.add(batch)
            batches.append(batch)
        session.commit()
        for batch in batches:
            session.refresh(batch)

        job_snapshot = CodingJob.model_validate(job, from_attributes=True)
        batch_snapshots = [
            CodingBatch.model_validate(batch, from_attributes=True)
            for batch in batches
        ]

    return job_snapshot, batch_snapshots


def run_coding_job(
    *,
    workspace_root: Path,
    job_id: int,
    client: LLMClient,
    top_k: int = 10,
) -> None:
    engine = get_engine(workspace_root)

    with Session(engine) as session:
        job = session.exec(select(CodingJob).where(CodingJob.id == job_id)).first()
        if job is None:
            raise ValueError(f"CodingJob {job_id} not found")
        job.status = "running"
        session.add(job)
        session.commit()
        session.refresh(job)

    snippets = retrieve_project_knowledge(
        workspace_root=workspace_root,
        project_slug=job.project_slug,
        query=job.question_column,
        stages=["analysis"],
        top_k=top_k,
    )
    prompt = load_coding_prompt()
    continuation_prompt = _load_continuation_prompt()
    rolling_codebook: list[dict] = []

    with Session(engine) as session:
        batches = session.exec(
            select(CodingBatch).where(CodingBatch.job_id == job_id)
        ).all()
    batches = sorted(batches, key=lambda item: item.batch_index)

    for batch in batches:
        _run_single_batch(
            engine=engine,
            batch=batch,
            job=job,
            snippets=snippets,
            prompt=prompt,
            continuation_prompt=continuation_prompt,
            rolling_codebook=rolling_codebook,
            client=client,
        )

    with Session(engine) as session:
        job = session.exec(select(CodingJob).where(CodingJob.id == job_id)).first()
        if job is None:
            raise ValueError(f"CodingJob {job_id} not found")
        batches = session.exec(
            select(CodingBatch).where(CodingBatch.job_id == job_id)
        ).all()
        failed_batches = [batch for batch in batches if batch.status == "failed"]
        completed_batches = [batch for batch in batches if batch.status == "done"]

        if failed_batches and completed_batches:
            job.status = "partial"
        elif failed_batches and not completed_batches:
            job.status = "failed"
        else:
            job.status = "done"

        job.final_codebook_json = {"themes": rolling_codebook}
        job.finished_at = datetime.now(UTC)
        session.add(job)
        session.commit()


def _run_single_batch(
    *,
    engine,
    batch: CodingBatch,
    job: CodingJob,
    snippets: list[dict],
    prompt: str,
    continuation_prompt: str,
    rolling_codebook: list[dict],
    client: LLMClient,
) -> None:
    with Session(engine) as session:
        batch_record = session.exec(select(CodingBatch).where(CodingBatch.id == batch.id)).first()
        if batch_record is None:
            raise ValueError(f"CodingBatch {batch.id} not found")
        batch_record.status = "running"
        session.add(batch_record)
        session.commit()

    for attempt in range(MAX_RETRIES + 1):
        try:
            if rolling_codebook:
                codebook_text = json.dumps(rolling_codebook[:30], ensure_ascii=False)
                full_prompt = f"{continuation_prompt}\n\nExisting codebook:\n{codebook_text}"
            else:
                full_prompt = prompt

            context = build_coding_context(
                question=job.question_column,
                responses=batch.input_texts_json,
                knowledge_snippets=snippets,
            )
            parsed = parse_coding_response(client.generate(f"{full_prompt}\n\n{context}"))

            existing_theme_names = {theme["theme_name"] for theme in rolling_codebook}
            for theme in parsed["themes"]:
                if theme["theme_name"] not in existing_theme_names:
                    rolling_codebook.append(theme)
                    existing_theme_names.add(theme["theme_name"])

            with Session(engine) as session:
                batch_record = session.exec(select(CodingBatch).where(CodingBatch.id == batch.id)).first()
                job_record = session.exec(select(CodingJob).where(CodingJob.id == job.id)).first()
                if batch_record is None or job_record is None:
                    raise ValueError("Coding batch or job disappeared during execution")
                batch_record.status = "done"
                batch_record.output_codes_json = parsed
                session.add(batch_record)

                job_record.coded_responses += len(batch.input_texts_json)
                session.add(job_record)
                session.commit()
            return
        except Exception as exc:
            if attempt < MAX_RETRIES:
                time.sleep(2**attempt)
                with Session(engine) as session:
                    batch_record = session.exec(select(CodingBatch).where(CodingBatch.id == batch.id)).first()
                    if batch_record is None:
                        raise ValueError(f"CodingBatch {batch.id} not found")
                    batch_record.retry_count = attempt + 1
                    session.add(batch_record)
                    session.commit()
                continue

            with Session(engine) as session:
                batch_record = session.exec(select(CodingBatch).where(CodingBatch.id == batch.id)).first()
                if batch_record is None:
                    raise ValueError(f"CodingBatch {batch.id} not found")
                batch_record.status = "failed"
                batch_record.error_message = str(exc)
                session.add(batch_record)
                session.commit()
            return


def get_coding_job_status(*, workspace_root: Path, job_id: int) -> dict:
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        job = session.exec(select(CodingJob).where(CodingJob.id == job_id)).first()
        if job is None:
            raise ValueError(f"CodingJob {job_id} not found")
        batches = session.exec(
            select(CodingBatch).where(CodingBatch.job_id == job_id)
        ).all()

    completed_batches = [batch for batch in batches if batch.status == "done"]
    failed_batches = [batch for batch in batches if batch.status == "failed"]
    return {
        "status": job.status,
        "total_batches": len(batches),
        "completed_batches": len(completed_batches),
        "failed_batches": len(failed_batches),
        "coded_responses": job.coded_responses,
        "total_responses": job.total_responses,
        "final_codebook_json": job.final_codebook_json,
    }


def _load_continuation_prompt() -> str:
    prompt_path = (
        Path(__file__).resolve().parent.parent
        / "llm"
        / "prompts"
        / "open_text_coding_continuation.md"
    )
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return load_coding_prompt() + (
        "\n\n## Additional instruction\n"
        "You have an existing codebook from previous batches. "
        "Use the same theme names when applicable. "
        "If you encounter genuinely new themes, add them."
    )
