import os
import shutil
import tempfile
from pathlib import Path

import httpx

from game_survey_workbench.llm.client import OpenAICompatibleLLMClient
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file

try:
    from scripts.verify_local_http import run_local_server, seed_fixture_workspace
except ModuleNotFoundError:
    from verify_local_http import run_local_server, seed_fixture_workspace

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "stage2_closeout"
WORKSPACE_ROOT = Path(tempfile.gettempdir()) / "gsw-stage2-closeout"
PROJECT_SLUG = "demo"
PROJECT_NAME = "Stage 2 Closeout Demo"
QUESTIONNAIRE_GOAL = "Assess whether the season pass experience feels credible enough for repeat play."
INSIGHT_GOAL = "Identify the most credible blockers to season pass satisfaction and future conversion."
CODING_QUESTION = "How satisfied are you with the current season pass overall?"
DATASET_FILENAME = "season_pass_closeout.csv"


def seed_stage2_closeout_workspace(target: Path) -> None:
    seed_fixture_workspace(
        target,
        fixture_root=FIXTURE_ROOT,
        survey_filename=DATASET_FILENAME,
        dataset_filename=DATASET_FILENAME,
    )


def fake_llm_generate(self, prompt: str) -> str:
    if "Open Text Coding Prompt" in prompt:
        return (
            '{"themes": ['
            '{"theme_name": "Pacing Friction", "count": 2, "example_responses": ['
            '"I only stayed because I had already paid.", '
            '"Value is acceptable, but pacing still feels flat."'
            "]}, "
            '{"theme_name": "Reward Clarity", "count": 2, "example_responses": ['
            '"The pass feels confusing more than exciting.", '
            '"I will likely skip the next pass unless rewards improve."'
            "]}"
            '], "uncoded_count": 0}'
        )
    if "Insight Synthesis Prompt" in prompt:
        return (
            "Season pass sentiment is dragged down by a mix of pacing friction and weak reward clarity. "
            "Deterministic satisfaction signals and coded verbatims both point to grind concerns, unclear unlock value, "
            "and low excitement near the end of the reward ladder."
        )
    return (
        "# Questionnaire Draft\n\n"
        "## Core Questions\n"
        "- How clear is the reward ladder for different player segments?\n"
        "- Which moments in the season pass feel most worth the effort?\n"
        "- What makes players consider skipping the next pass?\n"
    )


def configure_fake_llm_environment() -> dict[str, str | None]:
    original = {
        "GAME_SURVEY_WORKBENCH_LLM_PROVIDER": os.environ.get("GAME_SURVEY_WORKBENCH_LLM_PROVIDER"),
        "GAME_SURVEY_WORKBENCH_LLM_MODEL": os.environ.get("GAME_SURVEY_WORKBENCH_LLM_MODEL"),
        "GAME_SURVEY_WORKBENCH_LLM_API_KEY": os.environ.get("GAME_SURVEY_WORKBENCH_LLM_API_KEY"),
        "GAME_SURVEY_WORKBENCH_LLM_BASE_URL": os.environ.get("GAME_SURVEY_WORKBENCH_LLM_BASE_URL"),
    }
    os.environ["GAME_SURVEY_WORKBENCH_LLM_PROVIDER"] = "openai_compatible"
    os.environ["GAME_SURVEY_WORKBENCH_LLM_MODEL"] = "stage2-closeout-demo"
    os.environ["GAME_SURVEY_WORKBENCH_LLM_API_KEY"] = "test-key"
    os.environ["GAME_SURVEY_WORKBENCH_LLM_BASE_URL"] = "https://example.com/v1"
    return original


def restore_environment(values: dict[str, str | None]) -> None:
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def ingest_closeout_knowledge(workspace_root: Path) -> None:
    for source in (workspace_root / "knowledge").glob("*.md"):
        ingest_knowledge_file(source, project_root=workspace_root)


def run_stage2_closeout_assessment() -> dict[str, str | bool | int]:
    if WORKSPACE_ROOT.exists():
        shutil.rmtree(WORKSPACE_ROOT)
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

    previous_workspace_root = os.environ.get("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT")
    os.environ["GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT"] = str(WORKSPACE_ROOT)
    original_llm_env = configure_fake_llm_environment()
    original_generate = OpenAICompatibleLLMClient.generate
    OpenAICompatibleLLMClient.generate = fake_llm_generate

    try:
        seed_stage2_closeout_workspace(WORKSPACE_ROOT)
        ingest_closeout_knowledge(WORKSPACE_ROOT)

        with run_local_server(port=8766) as base_url:
            httpx.post(
                f"{base_url}/projects",
                json={"slug": PROJECT_SLUG, "name": PROJECT_NAME, "knowledge_pack": {}},
                timeout=5.0,
            ).raise_for_status()

            draft = httpx.post(
                f"{base_url}/projects/{PROJECT_SLUG}/questionnaires/draft",
                json={"research_goal": QUESTIONNAIRE_GOAL},
                timeout=5.0,
            )
            draft.raise_for_status()
            draft_payload = draft.json()
            questionnaire_path = (
                WORKSPACE_ROOT
                / "projects"
                / PROJECT_SLUG
                / "questionnaire"
                / "versions"
                / f"{draft_payload['version_id']}.md"
            )

            dataset_path = WORKSPACE_ROOT / "projects" / PROJECT_SLUG / "data" / "raw" / DATASET_FILENAME
            dataset = httpx.post(
                f"{base_url}/projects/{PROJECT_SLUG}/datasets/import",
                files={"file": (DATASET_FILENAME, dataset_path.read_bytes(), "text/csv")},
                timeout=5.0,
            )
            dataset.raise_for_status()
            dataset_payload = dataset.json()
            analysis_run_id = dataset_payload["analysis_run_id"]

            coding = httpx.post(
                f"{base_url}/projects/{PROJECT_SLUG}/analysis/{analysis_run_id}/code-text",
                json={"question_column": CODING_QUESTION},
                timeout=5.0,
            )
            coding.raise_for_status()
            coding_payload = coding.json()

            insights = httpx.post(
                f"{base_url}/projects/{PROJECT_SLUG}/analysis/{analysis_run_id}/insights",
                json={"research_goal": INSIGHT_GOAL},
                timeout=5.0,
            )
            insights.raise_for_status()
            insight_payload = insights.json()

            report = httpx.post(
                f"{base_url}/projects/{PROJECT_SLUG}/reports/generate",
                json={"analysis_run_id": analysis_run_id},
                timeout=5.0,
            )
            report.raise_for_status()
            report_payload = report.json()

        report_path = Path(report_payload["path"])
        report_markdown = report_path.read_text(encoding="utf-8")

        return {
            "QUESTIONNAIRE_PATH": str(questionnaire_path),
            "CODING_THEMES_PRESENT": bool(coding_payload["themes"]),
            "INSIGHT_EVIDENCE_PRESENT": bool(insight_payload["evidence_section"].strip()),
            "REPORT_EVIDENCE_SECTION_COUNT": report_markdown.count("## Evidence Basis"),
            "REPORT_PATH": str(report_path),
        }
    finally:
        OpenAICompatibleLLMClient.generate = original_generate
        restore_environment(original_llm_env)
        if previous_workspace_root is None:
            os.environ.pop("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", None)
        else:
            os.environ["GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT"] = previous_workspace_root


def main() -> None:
    results = run_stage2_closeout_assessment()
    for key, value in results.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
