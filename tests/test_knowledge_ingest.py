from pathlib import Path

from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file


def test_ingest_knowledge_file_returns_chunk_count(tmp_path: Path):
    source = tmp_path / "doc.md"
    source.write_text("# Title\n\nParagraph one.\n\nParagraph two.", encoding="utf-8")

    result = ingest_knowledge_file(source, project_root=tmp_path)

    assert result.document_title == "Title"
    assert result.chunk_count >= 1
