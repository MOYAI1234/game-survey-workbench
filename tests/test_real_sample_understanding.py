from pathlib import Path

from game_survey_workbench.services.dataset_import import import_dataset


WC_FIXTURE = Path(__file__).parent / "fixtures" / "surveys" / "wc_pass_sample.csv"
BB_FIXTURE = Path(__file__).parent / "fixtures" / "surveys" / "bb_stress_sample.csv"


def test_bb_real_sample_treats_segment_column_as_metadata(tmp_path: Path):
    dataset = import_dataset(BB_FIXTURE, project_slug="bb", workspace_root=tmp_path)

    assert "分层" not in dataset.question_columns


def test_wc_real_sample_uses_declared_types_from_second_header_row(tmp_path: Path):
    dataset = import_dataset(WC_FIXTURE, project_slug="wc", workspace_root=tmp_path)

    assert (
        dataset.question_columns["What are your most satisfying parts of Season Pass?"].question_type
        == "multi_select"
    )
    assert (
        dataset.question_columns[
            "Feel free to tell us what rewards you want to see in the Season Pass! You could also give us more suggestion about the game here!"
        ].question_type
        == "free_text"
    )
