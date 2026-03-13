from pathlib import Path

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.knowledge_ingest import (
    ingest_knowledge_file,
    retrieve_project_knowledge,
)
from game_survey_workbench.services.projects import create_project


def test_retrieve_project_knowledge_uses_project_knowledge_pack_filters(tmp_path: Path):
    source = tmp_path / "doc.md"
    source.write_text(
        "---\n"
        "title: Retention Framework\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - design\n"
        "scenario: onboarding\n"
        "---\n"
        "Use behavior and attitude questions together.\n",
        encoding="utf-8",
    )

    ingest_knowledge_file(source, project_root=tmp_path)
    create_project(
        ProjectCreate(
            slug="demo",
            name="Demo",
            knowledge_pack={"doc_types": ["theory"], "scenarios": ["onboarding"]},
        ),
        workspace_root=tmp_path,
    )

    results = retrieve_project_knowledge(
        workspace_root=tmp_path,
        project_slug="demo",
        query="behavior attitude questions",
        stages=["design"],
    )

    assert len(results) == 1
    assert results[0]["document_title"] == "Retention Framework"
