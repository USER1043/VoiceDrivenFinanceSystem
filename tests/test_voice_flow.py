from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_voice_budget_flow():
    response = client.post(
        "/voice",
        params={"text": "set food budget to 6000"}
    )

    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["intent"] == "UPDATE_BUDGET"
    assert data["data"]["category"] == "food"
    assert data["data"]["limit"] == 6000
