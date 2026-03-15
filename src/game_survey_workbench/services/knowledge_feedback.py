from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel


class KnowledgeFeedbackPayload(BaseModel):
    project_slug: str
    title: str
    key_findings: list[str]
    recommendations: list[str] | None = None
    source_report_path: str = ""


@dataclass
class KnowledgeFeedbackResult:
    file_path: Path
    document_title: str


def save_report_findings_as_knowledge(
    *,
    payload: KnowledgeFeedbackPayload,
    workspace_root: Path,
) -> KnowledgeFeedbackResult:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d")
    filename = f"{payload.project_slug}-findings-{timestamp}.md"

    knowledge_dir = workspace_root / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    file_path = knowledge_dir / filename

    frontmatter_lines = [
        "---",
        f"title: {payload.title}",
        "doc_type: experience",
        "stage:",
        "  - analysis",
        "  - report",
        "tags:",
        f"  - {payload.project_slug}",
        "  - findings",
        f"scenario: {payload.project_slug}",
        "priority: 3",
        "---",
    ]

    body_lines = [
        f"# {payload.title}",
        "",
        f"Source project: {payload.project_slug}",
    ]
    if payload.source_report_path:
        body_lines.append(f"Source report: {payload.source_report_path}")
    body_lines.extend(
        [
            f"Date: {timestamp}",
            "",
            "## Key Findings",
            "",
        ]
    )
    body_lines.extend(f"- {finding}" for finding in payload.key_findings)
    body_lines.append("")

    if payload.recommendations:
        body_lines.extend(
            [
                "## Recommendations",
                "",
            ]
        )
        body_lines.extend(f"- {recommendation}" for recommendation in payload.recommendations)
        body_lines.append("")

    content = "\n".join(frontmatter_lines) + "\n" + "\n".join(body_lines)
    file_path.write_text(content, encoding="utf-8")

    return KnowledgeFeedbackResult(
        file_path=file_path,
        document_title=payload.title,
    )
