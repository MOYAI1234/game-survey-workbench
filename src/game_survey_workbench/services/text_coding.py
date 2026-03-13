from __future__ import annotations

import json
from pathlib import Path


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
