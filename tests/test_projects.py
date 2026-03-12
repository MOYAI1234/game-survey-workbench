from fastapi.testclient import TestClient

from game_survey_workbench.app import create_app


def test_create_project_persists_selected_knowledge_filters():
    client = TestClient(create_app())

    response = client.post(
        "/projects",
        json={
            "slug": "new-player-onboarding",
            "name": "New Player Onboarding",
            "knowledge_pack": {
                "doc_types": ["theory", "industry"],
                "scenarios": ["onboarding"],
            },
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["slug"] == "new-player-onboarding"
    assert payload["knowledge_pack"]["scenarios"] == ["onboarding"]
