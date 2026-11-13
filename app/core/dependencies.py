from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.modules.users.models import Role, User

# auto_error=False — сами возвращаем 401 с понятным сообщением, если токена нет
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(db: DbSession, token: str | None = Depends(oauth2_scheme)) -> User:
    """Проверяет JWT и возвращает пользователя. 401 — если токена нет или он недействителен."""
    if not token:
        raise _unauthorized("Не передан токен авторизации")
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise _unauthorized("Недействительный или просроченный токен")

    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("Пользователь из токена не найден")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed_roles: Role) -> Callable[..., User]:
    """RBAC: пропускает только пользователей с одной из ролей, иначе 403."""

    def role_checker(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для выполнения операции",
            )
        return current_user

    return role_checker


AdminUser = Annotated[User, Depends(require_role(Role.admin))]
