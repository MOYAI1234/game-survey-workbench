import argparse
import os
import socket
import sys
import tempfile
from pathlib import Path

import httpx
from sqlmodel import Session, select

from game_survey_workbench.db import create_db_and_tables, get_engine
from game_survey_workbench.llm.client import OpenAICompatibleLLMClient
from game_survey_workbench.models.knowledge import KnowledgeDocument
from game_survey_workbench.services.knowledge_ingest import ingest_knowledge_file
from game_survey_workbench.services.project_knowledge import (
    replace_project_knowledge_selection,
)

try:
    from scripts.verify_local_http import run_local_server, seed_fixture_workspace
except ModuleNotFoundError:
    from verify_local_http import run_local_server, seed_fixture_workspace

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "stage2_closeout"
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


def select_all_ingested_knowledge_for_project(*, workspace_root: Path, project_slug: str) -> None:
    create_db_and_tables(workspace_root)
    engine = get_engine(workspace_root)
    with Session(engine) as session:
        document_ids = list(
            session.exec(select(KnowledgeDocument.id).order_by(KnowledgeDocument.id)).all()
        )
    if not document_ids:
        return
    replace_project_knowledge_selection(
        workspace_root=workspace_root,
        project_slug=project_slug,
        knowledge_document_ids=document_ids,
    )


def create_workspace_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="gsw-stage2-closeout-"))


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_stage2_closeout_assessment(mode: str = "scripted") -> dict[str, str | bool | int]:
    workspace_root = create_workspace_root()
    port = find_free_port()
    llm_route_timeout = 120.0 if mode == "provider" else 30.0

    previous_workspace_root = os.environ.get("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT")
    os.environ["GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT"] = str(workspace_root)

    original_generate = None
    original_llm_env = None

    if mode == "scripted":
        original_llm_env = configure_fake_llm_environment()
        original_generate = OpenAICompatibleLLMClient.generate
        OpenAICompatibleLLMClient.generate = fake_llm_generate
    else:
        required_vars = [
            "GAME_SURVEY_WORKBENCH_LLM_PROVIDER",
            "GAME_SURVEY_WORKBENCH_LLM_MODEL",
            "GAME_SURVEY_WORKBENCH_LLM_API_KEY",
            "GAME_SURVEY_WORKBENCH_LLM_BASE_URL",
        ]
        missing = [variable for variable in required_vars if not os.environ.get(variable)]
        if missing:
            raise RuntimeError(
                f"Provider mode requires these environment variables: {', '.join(missing)}"
            )

    try:
        seed_stage2_closeout_workspace(workspace_root)
        ingest_closeout_knowledge(workspace_root)

        with run_local_server(port=port) as base_url:
            httpx.post(
                f"{base_url}/projects",
                json={"slug": PROJECT_SLUG, "name": PROJECT_NAME, "knowledge_pack": {}},
                timeout=5.0,
            ).raise_for_status()
            select_all_ingested_knowledge_for_project(
                workspace_root=workspace_root,
                project_slug=PROJECT_SLUG,
            )

            draft = httpx.post(
                f"{base_url}/projects/{PROJECT_SLUG}/questionnaires/draft",
                json={"research_goal": QUESTIONNAIRE_GOAL},
                timeout=llm_route_timeout,
            )
            draft.raise_for_status()
            draft_payload = draft.json()
            questionnaire_path = (
                workspace_root
                / "projects"
                / PROJECT_SLUG
                / "questionnaire"
                / "versions"
                / f"{draft_payload['version_id']}.md"
            )
            questionnaire_markdown = questionnaire_path.read_text(encoding="utf-8")

            dataset_path = workspace_root / "projects" / PROJECT_SLUG / "data" / "raw" / DATASET_FILENAME
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
                timeout=llm_route_timeout,
            )
            coding.raise_for_status()
            coding_payload = coding.json()

            insights = httpx.post(
                f"{base_url}/projects/{PROJECT_SLUG}/analysis/{analysis_run_id}/insights",
                json={"research_goal": INSIGHT_GOAL},
                timeout=llm_route_timeout,
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
            "MODE": mode,
            "QUESTIONNAIRE_PATH": str(questionnaire_path),
            "QUESTIONNAIRE_HAS_KNOWLEDGE_BASIS": "## Knowledge Basis" in questionnaire_markdown,
            "CODING_THEMES_PRESENT": bool(coding_payload["themes"]),
            "INSIGHT_EVIDENCE_PRESENT": bool(insight_payload["evidence_section"].strip()),
            "REPORT_EVIDENCE_SECTION_COUNT": (
                report_markdown.count("## Evidence Basis")
                + report_markdown.count("## 证据基础")
            ),
            "REPORT_PATH": str(report_path),
        }
    finally:
        if original_generate is not None:
            OpenAICompatibleLLMClient.generate = original_generate
        if original_llm_env is not None:
            restore_environment(original_llm_env)
        if previous_workspace_root is None:
            os.environ.pop("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", None)
        else:
            os.environ["GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT"] = previous_workspace_root


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage 2 closeout assessment")
    parser.add_argument(
        "--mode",
        choices=["scripted", "provider"],
        default="scripted",
        help="scripted (default): use fake LLM output; provider: use real configured LLM",
    )
    args = parser.parse_args(sys.argv[1:])

    results = run_stage2_closeout_assessment(mode=args.mode)
    for key, value in results.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
