import time
from typing import Optional

import bcrypt
import jwt
from fastapi import Cookie, HTTPException, status

from .config import settings

COOKIE_NAME = "trace_session"
ALGO = "HS256"


def verify_password(password: str) -> bool:
    if not settings.trace_password_hash:
        return False
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            settings.trace_password_hash.encode("utf-8"),
        )
    except ValueError:
        return False


def issue_token(username: str) -> tuple[str, int]:
    """Returns (jwt, max_age_seconds)."""
    max_age = settings.trace_session_hours * 3600
    now = int(time.time())
    payload = {"sub": username, "iat": now, "exp": now + max_age}
    token = jwt.encode(payload, settings.trace_jwt_secret, algorithm=ALGO)
    return token, max_age


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.trace_jwt_secret, algorithms=[ALGO])
    except jwt.PyJWTError:
        return None


async def require_user(trace_session: Optional[str] = Cookie(default=None)) -> str:
    if not trace_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    payload = decode_token(trace_session)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session")
    return payload.get("sub", "")
