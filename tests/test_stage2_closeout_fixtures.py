from pathlib import Path


def test_stage2_closeout_fixtures_include_knowledge_and_survey_inputs():
    root = Path("tests/fixtures/stage2_closeout")

    assert (root / "README.md").exists()
    assert any((root / "knowledge").glob("*.md"))
    assert any((root / "surveys").glob("*.csv"))
