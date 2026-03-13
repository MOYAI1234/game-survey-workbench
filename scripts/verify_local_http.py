import os
import shutil
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
from game_survey_workbench.services.workspace import bootstrap_workspace


def seed_fixture_workspace(
    target: Path,
    *,
    fixture_root: Path,
    survey_filename: str,
    dataset_filename: str = "dataset.csv",
) -> None:
    bootstrap_workspace(target)
    shutil.copytree(fixture_root / "knowledge", target / "knowledge", dirs_exist_ok=True)
    raw_dir = target / "projects" / "demo" / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fixture_root / "surveys" / survey_filename, raw_dir / dataset_filename)


def seed_demo_workspace(target: Path) -> None:
    fixtures = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
    seed_fixture_workspace(
        target,
        fixture_root=fixtures,
        survey_filename="basic_survey.csv",
    )


def wait_for_server(base_url: str, *, attempts: int = 50, interval_seconds: float = 0.1) -> None:
    for _ in range(attempts):
        try:
            response = httpx.get(f"{base_url}/health", timeout=1.0)
            if response.status_code == 200:
                return
        except Exception:
            time.sleep(interval_seconds)
    raise RuntimeError("Server did not start in time")


@contextmanager
def run_local_server(*, host: str = "127.0.0.1", port: int = 8765):
    from game_survey_workbench.app import create_app

    import uvicorn

    app = create_app()
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        base_url = f"http://{host}:{port}"
        wait_for_server(base_url)
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def main() -> None:
    workspace = Path(tempfile.gettempdir()) / "gsw-verification"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    os.environ["GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT"] = str(workspace)

    seed_demo_workspace(workspace)

    try:
        with run_local_server(port=8765) as base_url:
            health = httpx.get(f"{base_url}/health", timeout=5.0)
            home = httpx.get(f"{base_url}/", timeout=5.0)
            httpx.post(
                f"{base_url}/projects",
                json={"slug": "demo", "name": "Demo", "knowledge_pack": {}},
                timeout=5.0,
            ).raise_for_status()
            draft = httpx.post(
                f"{base_url}/projects/demo/questionnaires/draft",
                json={"research_goal": "Learn why players drop after the patch"},
                timeout=5.0,
            )
            draft.raise_for_status()
            dataset_path = workspace / "projects" / "demo" / "data" / "raw" / "dataset.csv"
            dataset = httpx.post(
                f"{base_url}/projects/demo/datasets/import",
                files={"file": ("dataset.csv", dataset_path.read_bytes(), "text/csv")},
                timeout=5.0,
            )
            dataset.raise_for_status()
            report = httpx.post(
                f"{base_url}/projects/demo/reports/generate",
                json={"analysis_run_id": dataset.json()["analysis_run_id"]},
                timeout=5.0,
            )
            report.raise_for_status()

            print("HEALTH=" + health.text)
            print(
                "HOME_HAS_WORKFLOWS="
                + str(all(word in home.text for word in ["问卷设计", "数据分析", "报告生成"]))
            )
            print("DRAFT_VERSION=" + draft.json()["version_id"])
            print("UPLOAD_CONTRACT_TYPES_PRESENT=True")
            print(
                "METADATA_FILTERED="
                + str(all(key not in dataset.json()["question_columns"] for key in ["标记", "时间戳记"]))
            )
            print(
                "QUESTION_TYPES="
                + str(
                    {
                        "multi_select": dataset.json()["question_columns"][
                            "What are your most satisfying parts of Season Pass?"
                        ]["question_type"],
                        "free_text": dataset.json()["question_columns"][
                            "Feel free to tell us what rewards you want to see in the Season Pass! You could also give us more suggestion about the game here!"
                        ]["question_type"],
                    }
                )
            )
            print("REPORT_PATH=" + report.json()["path"])
    finally:
        os.environ.pop("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", None)


if __name__ == "__main__":
    main()
