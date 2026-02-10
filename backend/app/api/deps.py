from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.role import Role
from app.models.user import User
from app.services.rbac import has_permission


settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    claims = decode_access_token(token)
    if not claims:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")

    user_email = claims.get("sub")
    token_version = int(claims.get("ver", 0))

    user = db.scalar(select(User).where(User.email == user_email))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo")
    if user.token_version != token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesion expirada")
    return user


def require_permission(permission: str) -> Callable:
    def checker(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        role = db.scalar(select(Role).where(Role.id == current_user.role_id))
        if not role or not has_permission(role.permissions, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")
        return current_user

    return checker


def log_action(db: Session, user_id: int, action: str, resource: str, detail: str = "") -> None:
    db.add(AuditLog(user_id=user_id, action=action, resource=resource, detail=detail))
    db.commit()
