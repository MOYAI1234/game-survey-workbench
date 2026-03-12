from dataclasses import dataclass

import frontmatter


@dataclass
class ParsedKnowledgeDocument:
    title: str
    doc_type: str
    stages: list[str]
    body: str


def parse_markdown_document(raw: str) -> ParsedKnowledgeDocument:
    post = frontmatter.loads(raw)
    stage = post.get("stage", [])
    if isinstance(stage, str):
        stages = [stage]
    else:
        stages = list(stage)

    return ParsedKnowledgeDocument(
        title=post.get("title", "Untitled"),
        doc_type=post.get("doc_type", "experience"),
        stages=stages,
        body=post.content.strip(),
    )
