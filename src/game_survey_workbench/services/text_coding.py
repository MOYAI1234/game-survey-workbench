from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.errors import (
    CodingResponseFormatError,
    ProjectNotFoundError,
)
from game_survey_workbench.llm.client import LLMClient
from game_survey_workbench.models.text_coding import CodingResult
from game_survey_workbench.retrieval.store import DEFAULT_PROJECT_KNOWLEDGE_TOP_K
from game_survey_workbench.services.analysis_context import NoFreeTextResponsesFoundError
from game_survey_workbench.services.knowledge_ingest import retrieve_project_knowledge
from game_survey_workbench.services.projects import get_project


def format_knowledge_item(item: str | dict) -> str:
    if isinstance(item, str):
        return item

    title = item.get("document_title", "Unknown Source")
    content = item.get("content", "").strip()
    tags = item.get("tags", [])
    tag_text = f" [tags: {', '.join(tags)}]" if tags else ""
    return f"{title}{tag_text}: {content}".strip()


def build_coding_context(
    *,
    question: str,
    responses: list[str],
    knowledge_snippets: list[str | dict],
) -> str:
    sections = [
        f"Question: {question}",
        "Responses:",
        *[f"- {response}" for response in responses[:100]],
        "Knowledge:",
        *[f"- {format_knowledge_item(item)}" for item in knowledge_snippets],
    ]
    return "\n".join(sections)


def load_coding_prompt() -> str:
    prompt_path = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "open_text_coding.md"
    return prompt_path.read_text(encoding="utf-8").strip()


def parse_coding_response(raw_output: str) -> dict:
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise CodingResponseFormatError("LLM coding response was not valid JSON.") from exc

    themes = payload.get("themes")
    if not isinstance(themes, list):
        raise CodingResponseFormatError("LLM coding response must include a themes list.")

    uncoded_count = payload.get("uncoded_count", 0)
    if not isinstance(uncoded_count, int):
        raise CodingResponseFormatError("LLM coding response uncoded_count must be an integer.")

    normalized_themes: list[dict] = []
    for theme in themes:
        if not isinstance(theme, dict):
            raise CodingResponseFormatError("Each coded theme must be an object.")

        theme_name = theme.get("theme_name")
        count = theme.get("count")
        example_responses = theme.get("example_responses")
        if not isinstance(theme_name, str) or not theme_name.strip():
            raise CodingResponseFormatError("Each coded theme must include a non-empty theme_name.")
        if not isinstance(count, int):
            raise CodingResponseFormatError("Each coded theme must include an integer count.")
        if not isinstance(example_responses, list) or not all(
            isinstance(response, str) for response in example_responses
        ):
            raise CodingResponseFormatError(
                "Each coded theme must include example_responses as a list of strings."
            )
        normalized_themes.append(
            {
                **theme,
                "theme_name": theme_name.strip(),
                "count": count,
                "example_responses": example_responses,
            }
        )

    return {
        "themes": normalized_themes,
        "uncoded_count": uncoded_count,
    }


def save_coding_result(*, workspace_root: Path, result: CodingResult) -> CodingResult:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        session.add(result)
        session.commit()
        session.refresh(result)
        return result


def code_open_text_column(
    *,
    project_slug: str,
    analysis_run_id: str,
    question_column: str,
    responses: list[str],
    workspace_root: Path,
    client: LLMClient,
    top_k: int = DEFAULT_PROJECT_KNOWLEDGE_TOP_K,
) -> CodingResult:
    clean_responses = [response.strip() for response in responses if response and response.strip()]
    if not clean_responses:
        raise NoFreeTextResponsesFoundError(f"No free-text responses found for '{question_column}'.")

    project = get_project(workspace_root=workspace_root, project_slug=project_slug)
    if project is None:
        raise ProjectNotFoundError("Project not found.")

    from game_survey_workbench.services.batched_coding import (
        DEFAULT_BATCH_SIZE,
        create_coding_job,
        get_coding_job_status,
        run_coding_job,
    )

    if len(clean_responses) <= DEFAULT_BATCH_SIZE:
        return _code_single_batch(
            project_slug=project_slug,
            analysis_run_id=analysis_run_id,
            question_column=question_column,
            responses=clean_responses,
            workspace_root=workspace_root,
            client=client,
            top_k=top_k,
        )

    job, _batches = create_coding_job(
        workspace_root=workspace_root,
        project_slug=project_slug,
        analysis_run_id=analysis_run_id,
        question_column=question_column,
        responses=clean_responses,
    )
    run_coding_job(
        workspace_root=workspace_root,
        job_id=job.id,
        client=client,
        top_k=top_k,
    )
    status = get_coding_job_status(workspace_root=workspace_root, job_id=job.id)
    codebook = status.get("final_codebook_json") or {}
    snippets = retrieve_project_knowledge(
        workspace_root=workspace_root,
        project_slug=project_slug,
        query=question_column,
        stages=["analysis"],
        top_k=top_k,
    )
    if not snippets:
        snippets = retrieve_project_knowledge(
            workspace_root=workspace_root,
            project_slug=project_slug,
            query="",
            stages=["analysis"],
            top_k=top_k,
        )

    result = CodingResult(
        analysis_run_id=analysis_run_id,
        question_column=question_column,
        themes=codebook.get("themes", []),
        uncoded_count=sum(
            batch_output.get("uncoded_count", 0)
            for batch_output in _get_batch_outputs(workspace_root=workspace_root, job_id=job.id)
        ),
        citations=snippets,
    )
    return save_coding_result(workspace_root=workspace_root, result=result)


def _code_single_batch(
    *,
    project_slug: str,
    analysis_run_id: str,
    question_column: str,
    responses: list[str],
    workspace_root: Path,
    client: LLMClient,
    top_k: int = DEFAULT_PROJECT_KNOWLEDGE_TOP_K,
) -> CodingResult:
    snippets = retrieve_project_knowledge(
        workspace_root=workspace_root,
        project_slug=project_slug,
        query=question_column,
        stages=["analysis"],
        top_k=top_k,
    )
    if not snippets:
        snippets = retrieve_project_knowledge(
            workspace_root=workspace_root,
            project_slug=project_slug,
            query="",
            stages=["analysis"],
            top_k=top_k,
        )

    context = build_coding_context(
        question=question_column,
        responses=responses,
        knowledge_snippets=snippets,
    )
    prompt = load_coding_prompt()
    raw_output = client.generate(f"{prompt}\n\n{context}")
    parsed = parse_coding_response(raw_output)
    result = CodingResult(
        analysis_run_id=analysis_run_id,
        question_column=question_column,
        themes=parsed["themes"],
        uncoded_count=parsed["uncoded_count"],
        citations=snippets,
    )
    return save_coding_result(workspace_root=workspace_root, result=result)


def _get_batch_outputs(*, workspace_root: Path, job_id: int) -> list[dict]:
    from game_survey_workbench.models.coding_job import CodingBatch

    engine = get_engine(workspace_root)
    with Session(engine) as session:
        batches = session.exec(
            select(CodingBatch).where(CodingBatch.job_id == job_id)
        ).all()
    return [batch.output_codes_json for batch in batches if batch.output_codes_json]
