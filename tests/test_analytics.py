import pandas as pd

from game_survey_workbench.services.analytics import summarize_scale_question


def test_summarize_scale_question_returns_mean_and_top_box():
    series = pd.Series([5, 4, 5, 3, 4])

    summary = summarize_scale_question(series, top_box_values={4, 5})

    assert summary.mean == 4.2
    assert summary.top_box_rate == 0.8
