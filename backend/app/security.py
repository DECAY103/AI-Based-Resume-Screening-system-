"""JWT authentication and role guards shared by protected routes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import Cookie, Depends, Header, HTTPException, status
from jose import JWTError, jwt

from app.config import settings
from app.models import UserRole


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    email: str
    role: UserRole


async def current_user(
    authorization: str | None = Header(default=None),
    access_token: str | None = Cookie(default=None),
) -> CurrentUser:
    token = access_token
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        role = UserRole(payload["role"])
        return CurrentUser(user_id=payload["sub"], email=payload["email"], role=role)
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.") from exc


def require_roles(*roles: UserRole) -> Callable:
    async def guard(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
        return user
    return guard
