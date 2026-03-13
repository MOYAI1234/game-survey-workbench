from pathlib import Path

from game_survey_workbench.services.knowledge_ingest import (
    ingest_knowledge_file,
    retrieve_knowledge,
)


def test_ingest_knowledge_file_returns_chunk_count(tmp_path: Path):
    source = tmp_path / "doc.md"
    source.write_text("# Title\n\nParagraph one.\n\nParagraph two.", encoding="utf-8")

    result = ingest_knowledge_file(source, project_root=tmp_path)

    assert result.document_title == "Title"
    assert result.chunk_count >= 1


def test_ingest_knowledge_file_persists_scenario_and_tags(tmp_path: Path):
    source = tmp_path / "doc.md"
    source.write_text(
        "---\n"
        "title: Retention Framework\n"
        "doc_type: theory\n"
        "stage:\n"
        "  - analysis\n"
        "tags:\n"
        "  - retention\n"
        "scenario: onboarding\n"
        "---\n"
        "Players need clear goals.\n",
        encoding="utf-8",
    )

    ingest_knowledge_file(source, project_root=tmp_path)
    results = retrieve_knowledge(
        tmp_path,
        query="clear goals",
        stages=["analysis"],
        doc_types=["theory"],
        scenarios=["onboarding"],
    )

    assert results[0]["scenario"] == "onboarding"
    assert results[0]["tags"] == ["retention"]


def test_retrieve_knowledge_filters_out_non_matching_scenarios(tmp_path: Path):
    source = tmp_path / "doc.md"
    source.write_text(
        "---\n"
        "title: Event Framework\n"
        "doc_type: industry\n"
        "stage:\n"
        "  - design\n"
        "scenario: event\n"
        "---\n"
        "Reward expectations differ by event cadence.\n",
        encoding="utf-8",
    )

    ingest_knowledge_file(source, project_root=tmp_path)
    results = retrieve_knowledge(
        tmp_path,
        query="reward expectations",
        scenarios=["onboarding"],
    )

    assert results == []
