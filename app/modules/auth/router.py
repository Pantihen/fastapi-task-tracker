from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.dependencies import DbSession
from app.core.rate_limit import limiter
from app.modules.auth import service
from app.modules.auth.schemas import RegisterOut, Token, UserCreate
from app.modules.notifications import service as notifications_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Email уже зарегистрирован"}},
)
def register(data: UserCreate, db: DbSession) -> RegisterOut:
    """Регистрация. Пароль хешируется (bcrypt), роль — user.

    После регистрации в Celery ставится задача, которая создаёт приветственное уведомление.
    """
    user = service.register(db, data)
    job_id = notifications_service.queue_welcome(user.id)
    return RegisterOut.model_validate(user).model_copy(update={"welcome_job_id": job_id})


@router.post(
    "/login",
    response_model=Token,
    responses={401: {"description": "Неверный email или пароль"}, 429: {"description": "Слишком много попыток"}},
)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def login(
    request: Request,  # нужен slowapi для определения IP клиента
    db: DbSession,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    """Вход по OAuth2 Password Flow. В поле **username** передаётся email. Не чаще 5 раз в минуту с IP."""
    user = service.authenticate(db, form_data.username, form_data.password)
    return Token(access_token=service.issue_token(user))
