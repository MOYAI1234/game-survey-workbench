from contextlib import contextmanager
import importlib
from pathlib import Path

import httpx
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


def test_stage2_closeout_assessment_provider_mode_uses_extended_timeout_for_llm_routes(
    monkeypatch, tmp_path: Path
):
    module = importlib.import_module("scripts.run_stage2_closeout_assessment")
    timeouts = {}

    dataset_path = tmp_path / "projects" / module.PROJECT_SLUG / "data" / "raw"
    dataset_path.mkdir(parents=True, exist_ok=True)
    (dataset_path / module.DATASET_FILENAME).write_text("col\nvalue\n", encoding="utf-8")

    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_MODEL", "demo-model")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setattr(module, "create_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(module, "find_free_port", lambda: 9999)
    monkeypatch.setattr(module, "seed_stage2_closeout_workspace", lambda workspace_root: None)
    monkeypatch.setattr(module, "ingest_closeout_knowledge", lambda workspace_root: None)

    @contextmanager
    def fake_run_local_server(*, port):
        yield "http://127.0.0.1:9999"

    def fake_post(url, *, json=None, files=None, timeout=None):
        timeouts[url] = timeout

        if url.endswith("/projects"):
            return httpx.Response(200, request=httpx.Request("POST", url), json={})
        if url.endswith("/questionnaires/draft"):
            questionnaire_path = (
                tmp_path
                / "projects"
                / module.PROJECT_SLUG
                / "questionnaire"
                / "versions"
            )
            questionnaire_path.mkdir(parents=True, exist_ok=True)
            (questionnaire_path / "version-1.md").write_text(
                "# Draft\n\n## Knowledge Basis\n- Source: Evidence",
                encoding="utf-8",
            )
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"version_id": "version-1"},
            )
        if url.endswith("/datasets/import"):
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"analysis_run_id": "run-1"},
            )
        if url.endswith("/code-text"):
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"themes": [{"theme_name": "Theme", "count": 1}]},
            )
        if url.endswith("/insights"):
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"evidence_section": "## Evidence Basis\n- Source: Evidence"},
            )
        if url.endswith("/reports/generate"):
            report_path = tmp_path / "projects" / module.PROJECT_SLUG / "reports"
            report_path.mkdir(parents=True, exist_ok=True)
            report_file = report_path / "report-demo.md"
            report_file.write_text("## Evidence Basis\n- Source", encoding="utf-8")
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"path": str(report_file)},
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(module, "run_local_server", fake_run_local_server)
    monkeypatch.setattr(module.httpx, "post", fake_post)

    module.run_stage2_closeout_assessment(mode="provider")

    assert timeouts["http://127.0.0.1:9999/projects/demo/questionnaires/draft"] == 120.0
    assert timeouts["http://127.0.0.1:9999/projects/demo/analysis/run-1/code-text"] == 120.0
    assert timeouts["http://127.0.0.1:9999/projects/demo/analysis/run-1/insights"] == 120.0


def test_stage2_closeout_assessment_can_run_twice_in_same_process():
    module = importlib.import_module("scripts.run_stage2_closeout_assessment")

    first = module.run_stage2_closeout_assessment()
    second = module.run_stage2_closeout_assessment()

    assert first["QUESTIONNAIRE_HAS_KNOWLEDGE_BASIS"] is True
    assert second["QUESTIONNAIRE_HAS_KNOWLEDGE_BASIS"] is True
    assert first["QUESTIONNAIRE_PATH"] != second["QUESTIONNAIRE_PATH"]
