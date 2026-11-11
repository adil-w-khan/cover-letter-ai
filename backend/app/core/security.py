from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

from passlib.context import CryptContext
from jose import jwt, JWTError

from app.core.config import settings


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(
    password: str,
    password_hash: str
) -> bool:
    return pwd_context.verify(password, password_hash)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def access_expires() -> timedelta:
    return timedelta(
        minutes=settings.JWT_ACCESS_EXPIRES_MIN
    )


def refresh_expires() -> timedelta:
    return timedelta(
        days=settings.JWT_REFRESH_EXPIRES_DAYS
    )


def create_token(
    sub: str,
    token_type: str,
    expires_delta: timedelta,
    session_id: int | None = None
) -> str:
    now = utc_now()

    payload = {
        "sub": sub,
        "type": token_type,
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }

    if session_id is not None:
        payload["sid"] = session_id

    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=ALGORITHM
    )


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[ALGORITHM],
        options={"require_exp": True}
    )


def safe_token_type(
    payload: dict,
    expected: str
) -> bool:
    return payload.get("type") == expected


def token_identifier_hash(jti: str) -> str:
    return sha256(jti.encode("utf-8")).hexdigest()


def get_token_jti(token: str) -> str:
    payload = decode_token(token)

    jti = payload.get("jti")

    if not isinstance(jti, str) or not jti:
        raise JWTError("Missing token identifier")

    return jti