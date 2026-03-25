from pathlib import Path

from game_survey_workbench.models.project import ProjectCreate
from game_survey_workbench.retrieval.store import LocalVectorStore, StoredChunk
from game_survey_workbench.services.knowledge_ingest import (
    ingest_knowledge_file,
    retrieve_knowledge,
    retrieve_project_knowledge,
)
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)
from game_survey_workbench.services.projects import create_project


def test_query_respects_top_k_limit(tmp_path: Path):
    store = LocalVectorStore(tmp_path)
    store.save_chunks(
        [
            StoredChunk(
                document_title=f"Doc {index}",
                content=f"content {index}",
                stages=["analysis"],
                doc_type="theory",
                tags=[],
            )
            for index in range(20)
        ]
    )

    results = store.query("content", top_k=5)

    assert len(results) == 5


def test_retrieve_project_knowledge_only_uses_selected_documents(tmp_path: Path):
    selected_source = tmp_path / "selected-doc.md"
    selected_source.write_text(
        "---\n"
        "title: Retention Framework\n"
        "doc_type: guide\n"
        "stage:\n"
        "  - design\n"
        "---\n"
        "Use behavior and attitude questions together.\n",
        encoding="utf-8",
    )
    unselected_source = tmp_path / "unselected-doc.md"
    unselected_source.write_text(
        "---\n"
        "title: Unselected Doc\n"
        "doc_type: research\n"
        "stage:\n"
        "  - design\n"
        "---\n"
        "Pricing clarity matters for season pass conversion.\n",
        encoding="utf-8",
    )

    ingest_knowledge_file(selected_source, project_root=tmp_path)
    ingest_knowledge_file(unselected_source, project_root=tmp_path)
    create_project(
        ProjectCreate(
            slug="demo",
            name="Demo",
        ),
        workspace_root=tmp_path,
    )
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="demo",
        knowledge_document_ids=[1],
    )

    results = retrieve_project_knowledge(
        workspace_root=tmp_path,
        project_slug="demo",
        query="pricing clarity",
        stages=["design"],
    )

    assert len(results) == 1
    assert results[0]["document_title"] == "Retention Framework"
    assert all(item["document_title"] != "Unselected Doc" for item in results)


def test_retrieve_project_knowledge_forwards_top_k_limit(tmp_path: Path):
    for index in range(3):
        source = tmp_path / f"doc-{index}.md"
        source.write_text(
            "---\n"
            f"title: Analysis Doc {index}\n"
            "doc_type: theory\n"
            "stage:\n"
            "  - analysis\n"
            "scenario: churn\n"
            "---\n"
            f"analysis content {index}\n",
            encoding="utf-8",
        )
        ingest_knowledge_file(source, project_root=tmp_path)

    create_project(
        ProjectCreate(
            slug="demo",
            name="Demo",
        ),
        workspace_root=tmp_path,
    )
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="demo",
        knowledge_document_ids=[1, 2, 3],
    )

    results = retrieve_project_knowledge(
        workspace_root=tmp_path,
        project_slug="demo",
        query="analysis content",
        stages=["analysis"],
        top_k=2,
    )

    assert len(results) == 2


def test_retrieve_project_knowledge_defaults_to_at_most_20_results(tmp_path: Path):
    for index in range(25):
        source = tmp_path / f"guide-{index}.md"
        source.write_text(
            "---\n"
            f"title: Guide {index}\n"
            "doc_type: guide\n"
            "stage:\n"
            "  - design\n"
            "---\n"
            f"Use satisfaction diagnostics for version feedback {index}.\n",
            encoding="utf-8",
        )
        ingest_knowledge_file(source, project_root=tmp_path)

    create_project(
        ProjectCreate(
            slug="demo",
            name="Demo",
        ),
        workspace_root=tmp_path,
    )
    replace_project_knowledge_selection(
        workspace_root=tmp_path,
        project_slug="demo",
        knowledge_document_ids=list(range(1, 26)),
    )

    results = retrieve_project_knowledge(
        workspace_root=tmp_path,
        project_slug="demo",
        query="version satisfaction feedback",
        stages=["design"],
    )

    assert len(results) == 20
