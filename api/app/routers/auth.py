from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import auth
from app.config import Settings, get_settings
from app.db import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    auth.log_in(body.password, request, response, session, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    auth.log_out(request, response, session)
