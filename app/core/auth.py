from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings


class AuthUser:
    def __init__(self, sub: str, email: str | None, claims: dict[str, Any]):
        self.id = sub
        self.email = email
        self.claims = claims


async def require_user(authorization: str | None = Header(default=None)) -> AuthUser:
    settings = get_settings()

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )

    token = authorization.split(" ", 1)[1].strip()

    if not settings.supabase_jwt_secret:
        if settings.log_level.lower() == "debug":
            return AuthUser(sub="dev-user", email=None, claims={"dev": True})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_JWT_SECRET not configured",
        )

    try:
        claims = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc

    return AuthUser(sub=claims["sub"], email=claims.get("email"), claims=claims)


def optional_user(authorization: str | None = Header(default=None)) -> AuthUser | None:
    if not authorization:
        return None
    try:
        # reuse require_user logic synchronously where convenient
        import asyncio

        return asyncio.get_event_loop().run_until_complete(require_user(authorization))
    except HTTPException:
        return None
