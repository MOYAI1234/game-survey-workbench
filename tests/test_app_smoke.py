from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


def test_healthcheck_returns_ok():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
