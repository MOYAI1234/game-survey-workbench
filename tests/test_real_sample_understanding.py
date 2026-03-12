from pathlib import Path

from game_survey_workbench.services.dataset_import import import_dataset


FIXTURE = Path(__file__).parent / "fixtures" / "surveys" / "wc_pass_sample.csv"


def test_real_sample_fixture_marks_multiple_choice_and_free_text_correctly(tmp_path: Path):
    dataset = import_dataset(FIXTURE, project_slug="real-check", workspace_root=tmp_path)

    assert "标记" not in dataset.question_columns
    assert "时间戳记" not in dataset.question_columns
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
