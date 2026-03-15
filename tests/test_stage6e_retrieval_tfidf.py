"""TF-IDF weighted retrieval should rank domain-specific terms higher."""

from pathlib import Path

from game_survey_workbench.retrieval.store import LocalVectorStore, StoredChunk


def test_tfidf_prefers_rarer_term_over_tie_break_order(tmp_path: Path):
    store = LocalVectorStore(tmp_path / "artifacts" / "vector_store")
    store.save_chunks(
        [
            StoredChunk(
                document_title="Generic Purchase",
                content="game purchase habits across players",
                doc_type="experience",
                stages=["analysis"],
                tags=["overview"],
                scenario=None,
                priority=0,
            ),
            StoredChunk(
                document_title="Monetization Specific",
                content="monetization purchase behavior in live ops",
                doc_type="experience",
                stages=["analysis"],
                tags=["iap"],
                scenario=None,
                priority=0,
            ),
            StoredChunk(
                document_title="Gameplay Generic",
                content="game purchase loops and game rewards",
                doc_type="experience",
                stages=["analysis"],
                tags=["overview"],
                scenario=None,
                priority=0,
            ),
        ]
    )

    results = store.query("game purchase monetization", stages=["analysis"], top_k=3)

    assert results[0]["document_title"] == "Monetization Specific"


def test_query_returns_matches_for_common_term_after_tfidf_weighting(tmp_path: Path):
    store = LocalVectorStore(tmp_path / "artifacts" / "vector_store")
    store.save_chunks(
        [
            StoredChunk(
                document_title="Doc A",
                content="game economy overview",
                doc_type="experience",
                stages=["analysis"],
                tags=[],
                scenario=None,
                priority=0,
            ),
            StoredChunk(
                document_title="Doc B",
                content="game retention overview",
                doc_type="experience",
                stages=["analysis"],
                tags=[],
                scenario=None,
                priority=0,
            ),
        ]
    )

    results = store.query("game", stages=["analysis"], top_k=5)

    assert len(results) == 2


def test_query_keeps_chinese_retrieval_working(tmp_path: Path):
    store = LocalVectorStore(tmp_path / "artifacts" / "vector_store")
    store.save_chunks(
        [
            StoredChunk(
                document_title="中文文档",
                content="问卷设计需要结合玩家反馈",
                doc_type="experience",
                stages=["design"],
                tags=[],
                scenario=None,
                priority=0,
            )
        ]
    )

    results = store.query("问卷设计", stages=["design"], top_k=5)

    assert len(results) == 1
    assert results[0]["document_title"] == "中文文档"
