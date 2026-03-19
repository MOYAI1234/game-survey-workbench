from pathlib import Path

import pytest

from game_survey_workbench.services.upload_contract import (
    ALLOWED_TYPE_MARKERS,
    FormatDetectionResult,
    detect_format,
)


def test_detect_format_identifies_dual_header_csv(tmp_path: Path):
    csv = tmp_path / "dual.csv"
    csv.write_text(
        "Q1,Q2,Q3\n"
        "single_choice,free_text,scale\n"
        "A,hello,5\n"
        "B,world,3\n",
        encoding="utf-8",
    )

    result = detect_format(csv)

    assert isinstance(result, FormatDetectionResult)
    assert result.format_type == "dual_header"
    assert result.column_titles == ["Q1", "Q2", "Q3"]
    assert result.column_types == ["single_choice", "free_text", "scale"]


def test_detect_format_identifies_single_header_csv(tmp_path: Path):
    csv = tmp_path / "single.csv"
    csv.write_text(
        "Q1,Q2,Q3\n"
        "Male,I love this game,5\n"
        "Female,Great graphics,3\n"
        "Male,Fun gameplay,4\n",
        encoding="utf-8",
    )

    result = detect_format(csv)

    assert result.format_type == "single_header"
    assert result.column_titles == ["Q1", "Q2", "Q3"]
    assert len(result.inferred_columns) == 3
    for col in result.inferred_columns:
        assert col.inferred_type in ALLOWED_TYPE_MARKERS
        assert col.confidence in ("high", "medium", "low")
        assert col.reason


def test_detect_format_recognizes_wenjuanxing_multi_select_header(tmp_path: Path):
    csv = tmp_path / "wjx.csv"
    csv.write_text(
        "你最喜欢的功能是什么（多选）,你的建议（填空）\n"
        "A;B;C,很好\n"
        "A;D,还行\n",
        encoding="utf-8",
    )

    result = detect_format(csv)

    assert result.format_type == "single_header"
    assert result.inferred_columns[0].inferred_type == "multi_select"
    assert result.inferred_columns[1].inferred_type == "free_text"


def test_detect_format_raises_on_unreadable_file(tmp_path: Path):
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\x80\x81\x82")

    with pytest.raises(ValueError, match="Unsupported|cannot"):
        detect_format(bad)
