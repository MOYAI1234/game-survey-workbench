from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


def test_homepage_lists_three_primary_workflows():
    client = TestClient(create_app())

    response = client.get("/")

    body = response.text
    assert response.status_code == 200
    assert "问卷设计" in body
    assert "数据分析" in body
    assert "报告生成" in body
