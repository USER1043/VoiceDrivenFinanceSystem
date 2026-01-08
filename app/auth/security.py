from datetime import datetime, timedelta, timezone
from typing import Optional
import os

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

# -----------------------------
# LOAD ENV
# -----------------------------

load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60)
)

if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY not set in .env")

# -----------------------------
# PASSWORD HASHING
# -----------------------------

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# -----------------------------
# JWT TOKEN
# -----------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )

# -----------------------------
# CURRENT USER DEPENDENCY
# -----------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> int:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )

        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        return int(user_id)

    except JWTError:
        raise credentials_exception
