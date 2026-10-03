from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import CurrentUser
from app.config import Settings, get_settings

router = APIRouter(tags=["me"])


class MeOut(BaseModel):
    email: str
    timezone: str
    can_log_out: bool


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser, settings: Annotated[Settings, Depends(get_settings)]) -> MeOut:
    return MeOut(
        email=user.email, timezone=user.timezone, can_log_out=settings.auth_mode == "password"
    )
