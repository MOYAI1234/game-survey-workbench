from __future__ import annotations


def split_markdown(body: str, chunk_size: int = 800) -> list[str]:
    paragraphs = [item.strip() for item in body.split("\n\n") if item.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs or [body.strip()]:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if current and len(candidate) > chunk_size:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks
