from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..auth import COOKIE_NAME, issue_token, require_user, verify_password
from ..config import settings
from ..schemas import LoginRequest, Me

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Me)
async def login(req: LoginRequest, response: Response) -> Me:
    if req.username != settings.trace_user or not verify_password(req.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    token, max_age = issue_token(req.username)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.trace_cookie_secure,
        samesite="lax",
        domain=settings.trace_cookie_domain or None,
        path="/",
    )
    return Me(username=req.username)


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(
        key=COOKIE_NAME,
        domain=settings.trace_cookie_domain or None,
        path="/",
    )
    return {"ok": True}


@router.get("/me", response_model=Me)
async def me(username: str = Depends(require_user)) -> Me:
    return Me(username=username)
