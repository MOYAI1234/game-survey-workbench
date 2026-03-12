from game_survey_workbench.services.dataset_schema import classify_column


def test_classify_column_marks_timestamp_as_metadata():
    result = classify_column("时间戳记")

    assert result == "metadata"
