from app.api.routes.voice import handle_voice
from app.db.session import SessionLocal


def test_voice_budget_flow():
    db = SessionLocal()
    response = handle_voice(
        text="set food budget to 6000",
        db=db
    )

    assert response["success"] is True
    assert response["intent"] == "UPDATE_BUDGET"
    assert response["data"]["category"] == "food"
