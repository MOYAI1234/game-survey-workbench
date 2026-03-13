from game_survey_workbench.services.knowledge_parser import parse_markdown_document


def test_parse_markdown_document_extracts_frontmatter_and_body():
    raw = """---
title: Retention Framework
doc_type: theory
stage:
  - analysis
tags:
  - retention
scenario: onboarding
priority: 3
---
Body text here.
"""

    document = parse_markdown_document(raw)

    assert document.title == "Retention Framework"
    assert document.doc_type == "theory"
    assert document.stages == ["analysis"]
    assert document.tags == ["retention"]
    assert document.scenario == "onboarding"
    assert document.priority == 3
    assert document.body == "Body text here."
