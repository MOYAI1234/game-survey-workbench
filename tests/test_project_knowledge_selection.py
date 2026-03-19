from pathlib import Path

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.project_knowledge import (
    list_selected_knowledge_document_ids,
    replace_project_knowledge_selection,
)
from game_survey_workbench.services.projects import create_project


def _write_doc(path: Path, *, title: str, doc_type: str, stage: str, body: str) -> None:
    path.write_text(
        "---\n"
        f"title: {title}\n"
        f"doc_type: {doc_type}\n"
        "stage:\n"
        f"  - {stage}\n"
        "---\n"
        f"{body}\n",
        encoding="utf-8",
    )


def test_replace_project_knowledge_selection_persists_selected_document_ids(tmp_path: Path):
    create_project(
        ProjectCreate(slug="demo", name="Demo"),
        workspace_root=tmp_path,
    )
    first = tmp_path / "doc-one.md"
    second = tmp_path / "doc-two.md"
    _write_doc(
        first,
        title="Method Doc",
        doc_type="guide",
        stage="design",
        body="Method content.",
    )
    _write_doc(
        second,
        title="Domain Doc",
        doc_type="research",
        stage="analysis",
        body="Domain content.",
    )
    ingest_knowledge_file(first, project_root=tmp_path)
    ingest_knowledge_file(second, project_root=tmp_path)

    selected = replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="demo",
        knowledge_document_ids=[1, 2],
    )

    assert len(selected) == 2
    assert list_selected_knowledge_document_ids(
        workspace_root=tmp_path,
        project_slug="demo",
    ) == [1, 2]


def test_replace_project_knowledge_selection_replaces_existing_selection(tmp_path: Path):
    create_project(
        ProjectCreate(slug="demo", name="Demo"),
        workspace_root=tmp_path,
    )
    first = tmp_path / "doc-one.md"
    second = tmp_path / "doc-two.md"
    _write_doc(
        first,
        title="Method Doc",
        doc_type="guide",
        stage="design",
        body="Method content.",
    )
    _write_doc(
        second,
        title="Domain Doc",
        doc_type="research",
        stage="analysis",
        body="Domain content.",
    )
    ingest_knowledge_file(first, project_root=tmp_path)
    ingest_knowledge_file(second, project_root=tmp_path)

    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="demo",
        knowledge_document_ids=[1, 2],
    )

    selected = replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="demo",
        knowledge_document_ids=[2],
    )

    assert len(selected) == 1
    assert list_selected_knowledge_document_ids(
        workspace_root=tmp_path,
        project_slug="demo",
    ) == [2]
