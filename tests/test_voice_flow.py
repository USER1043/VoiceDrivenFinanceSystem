from app.api.routes.voice import handle_voice


def test_voice_budget_flow():
    response = handle_voice(
        text="set food budget to 6000",
        user_id=1
    )

    assert response["success"] is True
    assert response["intent"] == "UPDATE_BUDGET"
    assert response["data"]["category"] == "food"

