from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GAME_SURVEY_WORKBENCH_WORKSPACE_ROOT", str(tmp_path))
    with TestClient(create_app()) as test_client:
        yield test_client


def test_layout_nav_is_chinese(client: TestClient):
    response = client.get("/")

    assert response.status_code == 200
    assert "游戏问卷研究工作台" in response.text
