"""Admin authentication via signed cookie (independent of Starlette session)."""

from __future__ import annotations

import os

from fastapi import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

ADMIN_COOKIE = "adam_admin"
ADMIN_MAX_AGE = 7 * 24 * 3600


def _secret() -> str:
    secret = (os.getenv("SESSION_SECRET") or "dev-change-me-in-production").strip()
    return secret or "dev-change-me-in-production"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret(), salt="adam-admin-v1")


def is_admin(request: Request) -> bool:
    token = request.cookies.get(ADMIN_COOKIE)
    if not token:
        return bool(request.session.get("admin"))
    try:
        data = _serializer().loads(token, max_age=ADMIN_MAX_AGE)
        return bool(data.get("ok"))
    except (BadSignature, SignatureExpired):
        return False


def set_admin(response: Response) -> None:
    token = _serializer().dumps({"ok": True})
    secure = os.getenv("SESSION_COOKIE_SECURE", "").lower() in ("1", "true", "yes")
    response.set_cookie(
        ADMIN_COOKIE,
        token,
        max_age=ADMIN_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_admin(response: Response) -> None:
    response.delete_cookie(ADMIN_COOKIE, path="/")
