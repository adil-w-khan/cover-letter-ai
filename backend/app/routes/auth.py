from fastapi import (
    APIRouter, Depends, HTTPException,
    Response, Request
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from jose import JWTError

from app.db.session import get_db
from app.models.user import User
from app.models.refresh_session import RefreshSession

from app.core.config import settings
from app.core.limiter import limiter
from app.core.origin import require_allowed_origin

from app.core.security import (
    hash_password,
    verify_password,
    decode_token,
    safe_token_type,
    utc_now,
    refresh_expires
)

from app.services.auth_sessions import (
    issue_tokens,
    rotate_refresh_token,
    revoke_refresh_token
)

from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    UserOut
)


router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

REFRESH_COOKIE_NAME = "refresh_token"


def set_refresh_cookie(resp: Response, token: str):
    resp.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/auth",
        max_age=int(refresh_expires().total_seconds())
    )


def clear_refresh_cookie(resp: Response):
    resp.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/auth",
        secure=settings.COOKIE_SECURE,
        samesite="lax"
    )


def get_current_user(
    db: Session,
    authorization: str | None
) -> User:
    invalid = HTTPException(
        status_code=401,
        detail="Invalid access token"
    )

    if not authorization or not authorization.startswith("Bearer "):
        raise invalid

    token = authorization.split(" ", 1)[1].strip()

    try:
        payload = decode_token(token)

        if not safe_token_type(payload, "access"):
            raise invalid

        user_id = int(payload["sub"])
        session_id = int(payload["sid"])

    except (JWTError, ValueError, KeyError, TypeError):
        raise invalid

    session = db.query(RefreshSession).filter(
        RefreshSession.id == session_id,
        RefreshSession.user_id == user_id,
        RefreshSession.revoked_at.is_(None),
        RefreshSession.expires_at > utc_now()
    ).first()

    if not session:
        raise invalid

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise invalid

    return user


@router.post("/register", response_model=UserOut)
@limiter.limit("5/minute")
def register(
    request: Request,
    data: RegisterRequest,
    resp: Response,
    db: Session = Depends(get_db)
):
    email = data.email.strip().lower()

    if len(data.password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=422,
            detail="Password exceeds bcrypt's 72-byte limit"
        )

    user = User(
        email=email,
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password)
    )

    db.add(user)

    try:
        db.flush()
        access, refresh = issue_tokens(db, user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email already in use"
        )

    db.refresh(user)

    set_refresh_cookie(resp, refresh)
    resp.headers["X-Access-Token"] = access

    return user


@router.post("/login", response_model=UserOut)
@limiter.limit("10/minute")
def login(
    request: Request,
    data: LoginRequest,
    resp: Response,
    db: Session = Depends(get_db)
):
    email = data.email.strip().lower()

    user = db.query(User).filter(
        User.email == email
    ).first()

    valid_password = False

    if len(data.password.encode("utf-8")) <= 72 and user:
        valid_password = verify_password(
            data.password,
            user.password_hash
        )

    if not valid_password:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    access, refresh = issue_tokens(db, user)

    set_refresh_cookie(resp, refresh)
    resp.headers["X-Access-Token"] = access

    return user


@router.post("/refresh")
@limiter.limit("30/minute")
def refresh(
    request: Request,
    resp: Response,
    db: Session = Depends(get_db)
):
    require_allowed_origin(request)

    token = request.cookies.get(REFRESH_COOKIE_NAME)

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing refresh token"
        )

    access, new_refresh = rotate_refresh_token(
        db, token
    )

    set_refresh_cookie(resp, new_refresh)
    resp.headers["X-Access-Token"] = access

    return {"ok": True}


@router.post("/logout")
@limiter.limit("30/minute")
def logout(
    request: Request,
    resp: Response,
    db: Session = Depends(get_db)
):
    require_allowed_origin(request)

    token = request.cookies.get(REFRESH_COOKIE_NAME)

    if token:
        revoke_refresh_token(db, token)

    clear_refresh_cookie(resp)

    return {"ok": True}


@router.get("/me", response_model=UserOut)
@limiter.limit("60/minute")
def me(
    request: Request,
    db: Session = Depends(get_db)
):
    return get_current_user(
        db,
        request.headers.get("Authorization")
    )


@router.delete("/account")
@limiter.limit("5/minute")
def delete_account(
    request: Request,
    db: Session = Depends(get_db)
):
    user = get_current_user(
        db,
        request.headers.get("Authorization")
    )

    db.delete(user)
    db.commit()

    return {"ok": True}