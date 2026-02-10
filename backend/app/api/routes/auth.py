import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.password_reset_token import PasswordResetToken
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.user import UserRead
from app.services.bot import send_telegram_message
from app.services.rbac import parse_permissions


router = APIRouter()
settings = get_settings()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")

    token = create_access_token(subject=user.email, token_version=user.token_version)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserRead:
    role = db.scalar(select(Role).where(Role.id == current_user.role_id))
    role_name = role.name if role else "Sin rol"
    permissions = parse_permissions(role.permissions) if role else []
    return UserRead(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=role_name,
        permissions=permissions,
        preferred_language=current_user.preferred_language,
        preferred_currency=current_user.preferred_currency,
    )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    generic_message = "Si existe la cuenta, se enviaron instrucciones de recuperacion."
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not user.is_active or not user.telegram_chat_id:
        return MessageResponse(message=generic_message)

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_ttl_minutes)

    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            is_used=False,
        )
    )
    db.commit()

    reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?token={raw_token}"
    text = (
        "RIDAX recuperacion de contrasena\n"
        f"Enlace (expira en {settings.password_reset_ttl_minutes} min):\n{reset_url}"
    )
    await send_telegram_message(user.telegram_chat_id, text)

    return MessageResponse(message=generic_message)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    now = datetime.now(timezone.utc)
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    reset_token = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    if not reset_token or reset_token.is_used or reset_token.expires_at < now:
        raise HTTPException(status_code=400, detail="Token invalido o expirado")

    user = db.scalar(select(User).where(User.id == reset_token.user_id))
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.hashed_password = hash_password(payload.new_password)
    user.token_version += 1
    reset_token.is_used = True
    reset_token.used_at = now
    db.commit()
    return MessageResponse(message="Contrasena actualizada correctamente")
