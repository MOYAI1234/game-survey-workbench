from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(eq=True)
class ChunkResult:
    content: str
    heading_context: str
    chunk_index: int


HEADER_PATTERN = re.compile(r"^(#{1,3})\s+(.*\S)\s*$")


def split_markdown(
    content: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    respect_headers: bool = True,
) -> list[ChunkResult]:
    sections = _split_sections(content, respect_headers=respect_headers)
    chunks: list[ChunkResult] = []

    for heading_context, section_text in sections:
        for chunk_content in _split_section_text(
            section_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        ):
            chunks.append(
                ChunkResult(
                    content=chunk_content,
                    heading_context=heading_context,
                    chunk_index=len(chunks),
                )
            )

    return chunks


def _split_sections(content: str, *, respect_headers: bool) -> list[tuple[str, str]]:
    text = content.strip()
    if not text:
        return []
    if not respect_headers:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    heading_stack: list[str] = []
    current_context = ""
    current_lines: list[str] = []

    def flush_current() -> None:
        section_text = "\n".join(current_lines).strip()
        if section_text:
            sections.append((current_context, section_text))

    for line in text.splitlines():
        match = HEADER_PATTERN.match(line.strip())
        if match:
            flush_current()
            level = len(match.group(1))
            title = match.group(2).strip()
            heading_stack[:] = heading_stack[: level - 1]
            heading_stack.append(title)
            current_context = " > ".join(heading_stack)
            current_lines = []
            continue
        current_lines.append(line)

    flush_current()
    return sections


def _split_section_text(
    text: str,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    text_length = len(normalized)

    while start < text_length:
        remaining = text_length - start
        if remaining <= chunk_size:
            chunks.append(normalized[start:].strip())
            break

        window_end = start + chunk_size
        chunk_end = _find_breakpoint(normalized, start=start, window_end=window_end)
        chunk_text = normalized[start:chunk_end].strip()
        if not chunk_text:
            chunk_end = window_end
            chunk_text = normalized[start:chunk_end].strip()
        chunks.append(chunk_text)

        if chunk_end >= text_length:
            break

        next_start = chunk_end - min(chunk_overlap, max(len(chunk_text) - 1, 0))
        next_start = max(next_start, start + 1)
        while next_start < text_length and normalized[next_start].isspace():
            next_start += 1
        start = next_start

    return chunks


def _find_breakpoint(text: str, *, start: int, window_end: int) -> int:
    segment = text[start:window_end]
    for pattern in (r"\n\s*\n", r"[。？！.!?]", r"\s"):
        matches = list(re.finditer(pattern, segment))
        if matches:
            return start + matches[-1].end()
    return window_end
