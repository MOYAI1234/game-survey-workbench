from pathlib import Path

import pytest

from game_survey_workbench.services.upload_contract import parse_dual_header_dataframe


def test_parse_dual_header_dataframe_extracts_titles_types_and_rows(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "分层,Q1,Q2\n"
        "metadata,single_choice,free_text\n"
        "免费玩家,满意,希望奖励更多\n",
        encoding="utf-8",
    )

    parsed = parse_dual_header_dataframe(csv_path)

    assert parsed.column_titles == ["分层", "Q1", "Q2"]
    assert parsed.column_types == ["metadata", "single_choice", "free_text"]
    assert parsed.dataframe.iloc[0].to_dict() == {
        "分层": "免费玩家",
        "Q1": "满意",
        "Q2": "希望奖励更多",
    }


def test_parse_dual_header_dataframe_rejects_missing_type_row(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text("Q1,Q2\n满意,建议更多奖励\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Missing type marker row"):
        parse_dual_header_dataframe(csv_path)


def test_parse_dual_header_dataframe_rejects_unknown_type_marker(tmp_path: Path):
    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "Q1,Q2\nsingle_choice,matrix\n满意,高\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsupported type marker 'matrix'"):
        parse_dual_header_dataframe(csv_path)
