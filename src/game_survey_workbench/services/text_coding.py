from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.llm.client import LLMClient
from game_survey_workbench.models.text_coding import CodingResult
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
    except json.JSONDecodeError:
        return {"themes": [], "uncoded_count": 0}

    themes = payload.get("themes")
    if not isinstance(themes, list):
        themes = []

    uncoded_count = payload.get("uncoded_count", 0)
    if not isinstance(uncoded_count, int):
        uncoded_count = 0

    return {
        "themes": themes,
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
    top_k: int = 10,
) -> CodingResult:
    project = get_project(workspace_root=workspace_root, project_slug=project_slug)
    if project is None:
        raise ValueError("Project not found.")

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
    if not snippets:
        raise ValueError("No knowledge matched this text coding request.")

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
