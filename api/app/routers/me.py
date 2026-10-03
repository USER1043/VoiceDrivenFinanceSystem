from fastapi import APIRouter
from pydantic import BaseModel

from app.auth import CurrentUser

router = APIRouter(tags=["me"])


class MeOut(BaseModel):
    email: str
    name: str | None
    timezone: str
    is_admin: bool
    has_password: bool
    has_google: bool


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser) -> MeOut:
    return MeOut(
        email=user.email,
        name=user.name,
        timezone=user.timezone,
        is_admin=user.is_admin,
        has_password=user.password_hash is not None,
        has_google=user.google_sub is not None,
    )
