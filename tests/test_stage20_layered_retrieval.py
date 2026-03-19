from pathlib import Path

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.knowledge_ingest import (
    ingest_knowledge_file,
    retrieve_project_knowledge,
)
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)
from game_survey_workbench.services.projects import create_project


def test_retrieve_project_knowledge_combines_method_pool_and_domain_pool(tmp_path: Path):
    method_source = tmp_path / "method.md"
    method_source.write_text(
        "---\n"
        "title: Survey Method Guide\n"
        "doc_type: guide\n"
        "stage:\n"
        "  - design\n"
        "priority: 5\n"
        "---\n"
        "Use segmentation and diagnostic framing in questionnaire design.\n",
        encoding="utf-8",
    )
    domain_source = tmp_path / "domain.md"
    domain_source.write_text(
        "---\n"
        "title: Season Pass Research\n"
        "doc_type: research\n"
        "stage:\n"
        "  - design\n"
        "---\n"
        "Season pass value and pricing clarity affect conversion.\n",
        encoding="utf-8",
    )

    ingest_knowledge_file(method_source, project_root=tmp_path)
    ingest_knowledge_file(domain_source, project_root=tmp_path)
    create_project(
        ProjectCreate(slug="demo", name="Demo"),
        workspace_root=tmp_path,
    )
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="demo",
        knowledge_document_ids=[1, 2],
    )

    results = retrieve_project_knowledge(
        workspace_root=tmp_path,
        project_slug="demo",
        query="season pass value",
        stages=["design"],
    )

    assert any(item["retrieval_pool"] == "method" for item in results)
    assert any(item["retrieval_pool"] == "domain" for item in results)
