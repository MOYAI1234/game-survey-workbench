from pathlib import Path
import shutil

from game_survey_workbench.services.workspace import bootstrap_workspace


def seed_demo_workspace(target: Path) -> None:
    fixtures = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
    bootstrap_workspace(target)
    shutil.copytree(fixtures / "knowledge", target / "knowledge", dirs_exist_ok=True)
    raw_dir = target / "projects" / "demo" / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fixtures / "surveys" / "basic_survey.csv", raw_dir / "dataset.csv")


if __name__ == "__main__":
    seed_demo_workspace(Path("workspace"))
