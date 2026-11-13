from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.modules.auth.schemas import UserCreate
from app.modules.users import service as users_service
from app.modules.users.models import Role, User


def register(db: Session, data: UserCreate) -> User:
    email = data.email.lower()
    if users_service.get_by_email(db, email) is not None:
        raise ConflictError("Пользователь с таким email уже существует")

    # при самостоятельной регистрации роль всегда user — повысить может только admin
    user = User(email=email, hashed_password=hash_password(data.password), role=Role.user)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # гонка двух одновременных регистраций
        db.rollback()
        raise ConflictError("Пользователь с таким email уже существует")
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = users_service.get_by_email(db, email)
    # хеш-заглушка выравнивает время ответа: по нему нельзя понять, есть ли такой email
    password_ok = verify_password(password, user.hashed_password if user else DUMMY_HASH)
    if user is None or not password_ok:
        raise UnauthorizedError("Неверный email или пароль")
    return user


def issue_token(user: User) -> str:
    return create_access_token(subject=str(user.id), role=user.role.value)
