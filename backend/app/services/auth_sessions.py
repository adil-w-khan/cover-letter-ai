from datetime import timedelta

from fastapi import HTTPException
from jose import JWTError
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.refresh_session import RefreshSession
from app.core.security import (
    create_token,
    decode_token,
    get_token_jti,
    token_identifier_hash,
    access_expires,
    refresh_expires,
    safe_token_type,
    utc_now
)


def issue_tokens(db: Session, user: User):
    expires = utc_now() + refresh_expires()

    session = RefreshSession(
        user_id=user.id,
        token_hash="",
        expires_at=expires
    )

    db.add(session)
    db.flush()

    access = create_token(
        str(user.id),
        "access",
        access_expires(),
        session.id
    )

    refresh = create_token(
        str(user.id),
        "refresh",
        refresh_expires(),
        session.id
    )

    session.token_hash = token_identifier_hash(
        get_token_jti(refresh)
    )

    db.commit()

    return access, refresh


def rotate_refresh_token(db: Session, token: str):
    invalid = HTTPException(
        status_code=401,
        detail="Invalid or expired session"
    )

    try:
        payload = decode_token(token)

        if not safe_token_type(payload, "refresh"):
            raise invalid

        session_id = int(payload["sid"])
        user_id = int(payload["sub"])
        jti = payload["jti"]

        if not isinstance(jti, str) or not jti:
            raise invalid

    except (JWTError, ValueError, KeyError, TypeError):
        raise invalid

    session = (
        db.query(RefreshSession)
        .filter(RefreshSession.id == session_id)
        .with_for_update()
        .first()
    )

    if not session or session.user_id != user_id:
        raise invalid

    if session.revoked_at is not None:
        raise invalid

    if session.expires_at <= utc_now():
        raise invalid

    incoming_hash = token_identifier_hash(jti)

    if incoming_hash != session.token_hash:
        session.revoked_at = utc_now()
        db.commit()
        raise invalid

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise invalid

    remaining = session.expires_at - utc_now()

    if remaining <= timedelta(0):
        raise invalid

    new_access = create_token(
        str(user.id),
        "access",
        access_expires(),
        session.id
    )

    new_refresh = create_token(
        str(user.id),
        "refresh",
        remaining,
        session.id
    )

    session.token_hash = token_identifier_hash(
        get_token_jti(new_refresh)
    )

    db.commit()

    return new_access, new_refresh


def revoke_refresh_token(db: Session, token: str):
    try:
        payload = decode_token(token)

        if not safe_token_type(payload, "refresh"):
            return

        session_id = int(payload["sid"])
        user_id = int(payload["sub"])

    except (JWTError, ValueError, KeyError, TypeError):
        return

    session = (
        db.query(RefreshSession)
        .filter(
            RefreshSession.id == session_id,
            RefreshSession.user_id == user_id
        )
        .first()
    )

    if session and session.revoked_at is None:
        session.revoked_at = utc_now()
        db.commit()