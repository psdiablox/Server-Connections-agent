import secrets
from typing import Optional
from fastapi import Cookie, HTTPException
from fastapi.responses import RedirectResponse

ADMIN_USER = "admin"
ADMIN_PASS = "Rocketpower1"

_sessions: set[str] = set()


def create_session() -> str:
    token = secrets.token_hex(32)
    _sessions.add(token)
    return token


def revoke_session(token: str) -> None:
    _sessions.discard(token)


def require_auth(session: Optional[str] = Cookie(None)):
    if not session or session not in _sessions:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return session


def check_credentials(username: str, password: str) -> bool:
    return username == ADMIN_USER and password == ADMIN_PASS
