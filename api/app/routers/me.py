from fastapi import APIRouter
from pydantic import BaseModel

from app.auth import CurrentUser

router = APIRouter(tags=["me"])


class MeOut(BaseModel):
    email: str
    timezone: str


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser) -> MeOut:
    return MeOut(email=user.email, timezone=user.timezone)
