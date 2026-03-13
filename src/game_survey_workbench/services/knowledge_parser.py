from dataclasses import dataclass

import frontmatter


@dataclass
class ParsedKnowledgeDocument:
    title: str
    doc_type: str
    stages: list[str]
    tags: list[str]
    scenario: str | None
    priority: int
    body: str


def parse_markdown_document(raw: str) -> ParsedKnowledgeDocument:
    post = frontmatter.loads(raw)
    stage = post.get("stage", [])
    if isinstance(stage, str):
        stages = [stage]
    else:
        stages = list(stage)
    tags = post.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    return ParsedKnowledgeDocument(
        title=post.get("title", "Untitled"),
        doc_type=post.get("doc_type", "experience"),
        stages=stages,
        tags=list(tags),
        scenario=post.get("scenario"),
        priority=int(post.get("priority", 0)),
        body=post.content.strip(),
    )
