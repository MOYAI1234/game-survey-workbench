import importlib
import pytest


def test_stage2_closeout_assessment_script_emits_mode_metadata(monkeypatch, capsys):
    module = importlib.import_module("scripts.run_stage2_closeout_assessment")

    monkeypatch.setattr(
        module,
        "run_stage2_closeout_assessment",
        lambda mode: {
            "MODE": mode,
            "QUESTIONNAIRE_PATH": "workspace/projects/demo/questionnaire/versions/demo.md",
            "QUESTIONNAIRE_HAS_KNOWLEDGE_BASIS": True,
            "CODING_THEMES_PRESENT": True,
            "INSIGHT_EVIDENCE_PRESENT": True,
            "REPORT_EVIDENCE_SECTION_COUNT": 1,
            "REPORT_PATH": "workspace/projects/demo/reports/report-demo.md",
        },
    )
    monkeypatch.setattr("sys.argv", ["run_stage2_closeout_assessment.py"])

    module.main()
    output = capsys.readouterr().out

    assert "MODE=scripted" in output


def test_stage2_closeout_assessment_script_emits_key_artifact_paths(monkeypatch, capsys):
    module = importlib.import_module("scripts.run_stage2_closeout_assessment")

    monkeypatch.setattr(
        module,
        "run_stage2_closeout_assessment",
        lambda mode="scripted": {
            "MODE": "scripted",
            "QUESTIONNAIRE_PATH": "workspace/projects/demo/questionnaire/versions/demo.md",
            "CODING_THEMES_PRESENT": True,
            "INSIGHT_EVIDENCE_PRESENT": True,
            "REPORT_EVIDENCE_SECTION_COUNT": 1,
            "REPORT_PATH": "workspace/projects/demo/reports/report-demo.md",
        },
    )
    monkeypatch.setattr("sys.argv", ["run_stage2_closeout_assessment.py"])

    module.main()
    output = capsys.readouterr().out

    assert "MODE=" in output
    assert "QUESTIONNAIRE_PATH=" in output
    assert "CODING_THEMES_PRESENT=True" in output
    assert "INSIGHT_EVIDENCE_PRESENT=True" in output
    assert "REPORT_EVIDENCE_SECTION_COUNT=1" in output


def test_stage2_closeout_assessment_provider_mode_rejects_missing_credentials(monkeypatch):
    module = importlib.import_module("scripts.run_stage2_closeout_assessment")

    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", raising=False)
    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="Provider mode requires"):
        module.run_stage2_closeout_assessment(mode="provider")


def test_stage2_closeout_assessment_can_run_twice_in_same_process():
    module = importlib.import_module("scripts.run_stage2_closeout_assessment")

    first = module.run_stage2_closeout_assessment()
    second = module.run_stage2_closeout_assessment()

    assert first["QUESTIONNAIRE_HAS_KNOWLEDGE_BASIS"] is True
    assert second["QUESTIONNAIRE_HAS_KNOWLEDGE_BASIS"] is True
    assert first["QUESTIONNAIRE_PATH"] != second["QUESTIONNAIRE_PATH"]
