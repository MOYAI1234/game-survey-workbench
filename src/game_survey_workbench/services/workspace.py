from pathlib import Path


def bootstrap_workspace(root: Path) -> None:
    for name in ("knowledge", "projects", "artifacts"):
        (root / name).mkdir(parents=True, exist_ok=True)
