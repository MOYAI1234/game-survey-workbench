from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


def test_homepage_lists_three_primary_workflows():
    client = TestClient(create_app())

    response = client.get("/")

    body = response.text
    assert response.status_code == 200
    assert "项目列表" in body
    assert "共享知识库" in body
    assert "新建项目" in body
