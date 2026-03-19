from pathlib import Path

from sqlmodel import Session

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.models.knowledge import KnowledgeDocument


def test_knowledge_document_persists_source_format(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        doc = KnowledgeDocument(
            source_path="/knowledge/report.md",
            title="Converted Report",
            doc_type="research",
            source_format="pdf",
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)

        assert doc.source_format == "pdf"
        assert doc.id is not None


def test_knowledge_document_source_format_defaults_to_none(tmp_path: Path):
    create_db_and_tables(tmp_path)
    engine = get_engine(tmp_path)

    with Session(engine) as session:
        doc = KnowledgeDocument(
            source_path="/knowledge/manual.md",
            title="Manual Doc",
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)

        assert doc.source_format is None
