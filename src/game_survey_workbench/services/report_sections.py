"""Section-based report assembly."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReportSection:
    key: str
    title: str
    order: int
    content: str


class ReportSectionRegistry:
    """Ordered collection of report sections, keyed for replacement."""

    def __init__(self) -> None:
        self._sections: dict[str, ReportSection] = {}

    def register(self, section: ReportSection) -> None:
        self._sections[section.key] = section

    def ordered_sections(self) -> list[ReportSection]:
        return sorted(self._sections.values(), key=lambda section: section.order)

    def get(self, key: str) -> ReportSection | None:
        return self._sections.get(key)


def assemble_report_markdown(
    *,
    title: str,
    date: str,
    registry: ReportSectionRegistry,
) -> str:
    """Assemble a complete Markdown report from registered sections."""

    lines = [f"# {title}", "", f"*Report generated {date}*", ""]

    for section in registry.ordered_sections():
        if not section.content or not section.content.strip():
            continue
        lines.append(f"## {section.title}")
        lines.append("")
        lines.append(section.content)
        lines.append("")

    return "\n".join(lines)
