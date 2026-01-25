from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session
from jose import JWTError
from app.db.session import get_db
from app.models.user import User
from app.core.security import (
    hash_password, verify_password,
    create_token, decode_token,
    access_expires, refresh_expires, safe_token_type
)
from app.schemas.auth import RegisterRequest, LoginRequest, UserOut
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"

def set_refresh_cookie(resp: Response, token: str):
    resp.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
        max_age=int(refresh_expires().total_seconds()),
    )

def clear_refresh_cookie(resp: Response):
    resp.delete_cookie(key=REFRESH_COOKIE_NAME, path="/")

def get_current_user(db: Session, authorization: str | None) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing access token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
        if not safe_token_type(payload, "access"):
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = int(payload["sub"])
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid access token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@router.post("/register", response_model=UserOut)
def register(data: RegisterRequest, resp: Response, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use")

    user = User(
        email=data.email.lower(),
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access = create_token(str(user.id), "access", access_expires())
    refresh = create_token(str(user.id), "refresh", refresh_expires())
    set_refresh_cookie(resp, refresh)

    # Access token returned in body; refresh token in httpOnly cookie
    resp.headers["X-Access-Token"] = access
    return user

@router.post("/login", response_model=UserOut)
def login(data: LoginRequest, resp: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access = create_token(str(user.id), "access", access_expires())
    refresh = create_token(str(user.id), "refresh", refresh_expires())
    set_refresh_cookie(resp, refresh)
    resp.headers["X-Access-Token"] = access
    return user

@router.post("/refresh")
def refresh(req: Request, resp: Response):
    token = req.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        payload = decode_token(token)
        if not safe_token_type(payload, "refresh"):
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_access = create_token(str(user_id), "access", access_expires())
    resp.headers["X-Access-Token"] = new_access
    return {"ok": True}

@router.post("/logout")
def logout(resp: Response):
    clear_refresh_cookie(resp)
    return {"ok": True}

@router.get("/me", response_model=UserOut)
def me(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(db, request.headers.get("Authorization"))
    return user

@router.delete("/account")
def delete_account(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(db, request.headers.get("Authorization"))
    # hard delete user (cascade deletes cover letters)
    db.delete(user)
    db.commit()
    return {"ok": True}
