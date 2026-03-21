from game_survey_workbench.retrieval.chunking import ChunkResult, split_markdown


def test_split_markdown_respects_header_boundaries_and_heading_context():
    body = (
        "# 第一章\n\n"
        "这是章节一的导语。\n\n"
        "## 玩家动机\n\n"
        "玩家会因为成长感而回归。\n\n"
        "# 第二章\n\n"
        "第二章只谈留存。"
    )

    chunks = split_markdown(body, chunk_size=80, chunk_overlap=8)

    assert chunks == [
        ChunkResult(content="这是章节一的导语。", heading_context="第一章", chunk_index=0),
        ChunkResult(
            content="玩家会因为成长感而回归。",
            heading_context="第一章 > 玩家动机",
            chunk_index=1,
        ),
        ChunkResult(content="第二章只谈留存。", heading_context="第二章", chunk_index=2),
    ]


def test_split_markdown_adds_overlap_between_adjacent_chunks():
    body = "# 标题\n\n" + ("甲" * 30) + ("乙" * 30) + ("丙" * 30)

    chunks = split_markdown(body, chunk_size=40, chunk_overlap=10)

    assert len(chunks) >= 2
    assert chunks[0].content[-10:] == chunks[1].content[:10]


def test_split_markdown_assigns_monotonic_chunk_indexes():
    body = "# 标题\n\n" + ("玩家反馈。" * 20)

    chunks = split_markdown(body, chunk_size=30, chunk_overlap=6)

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
