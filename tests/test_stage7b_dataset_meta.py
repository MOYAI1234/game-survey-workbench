"""Extract dataset metadata for report context."""

from game_survey_workbench.services.dataset_meta import extract_dataset_meta


def test_extract_meta_from_schema():
    schema = {
        "columns": {
            "satisfaction": {"type": "scale"},
            "game_mode": {"type": "single_choice"},
            "feedback": {"type": "free_text"},
            "features": {"type": "multi_select"},
            "features_2": {"type": "multi_select"},
        }
    }

    meta = extract_dataset_meta(schema=schema, row_count=500)

    assert meta["row_count"] == 500
    assert meta["question_count"] == 5
    assert meta["question_types"]["scale"] == 1
    assert meta["question_types"]["single_choice"] == 1
    assert meta["question_types"]["free_text"] == 1
    assert meta["question_types"]["multi_select"] == 2


def test_extract_meta_empty_schema():
    meta = extract_dataset_meta(schema={}, row_count=0)

    assert meta["row_count"] == 0
    assert meta["question_count"] == 0
    assert meta["question_types"] == {}
