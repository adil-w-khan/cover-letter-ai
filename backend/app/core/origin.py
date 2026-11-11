from fastapi import HTTPException, Request

from app.core.config import settings


def require_allowed_origin(request: Request) -> None:
    origin = request.headers.get("origin")

    if origin not in settings.cors_list():
        raise HTTPException(
            status_code=403,
            detail="Origin not allowed"
        )