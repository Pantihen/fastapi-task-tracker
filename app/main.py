import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import SQLAlchemyError

import app.models  # noqa: F401 — регистрирует все модели до первого запроса
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import AppError, app_error_handler
from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.modules.auth.router import router as auth_router
from app.modules.health.router import router as health_router
from app.modules.notifications.router import router as notifications_router
from app.modules.projects.router import router as projects_router
from app.modules.tasks.router import router as tasks_router
from app.modules.users import service as users_service
from app.modules.users.models import Role, User
from app.modules.users.router import admin_router, router as users_router

logger = logging.getLogger(__name__)


def seed_admin() -> None:
    """Создаёт администратора из переменных окружения, если его ещё нет.

    Таблицы создаёт не приложение, а Alembic (`alembic upgrade head` перед стартом).
    """
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        return
    try:
        with SessionLocal() as db:
            if users_service.get_by_email(db, settings.ADMIN_EMAIL) is None:
                db.add(
                    User(
                        email=settings.ADMIN_EMAIL.lower(),
                        hashed_password=hash_password(settings.ADMIN_PASSWORD),
                        role=Role.admin,
                    )
                )
                db.commit()
    except SQLAlchemyError:
        logger.exception("Не удалось создать администратора — выполнены ли миграции (alembic upgrade head)?")


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed_admin()
    yield


app = FastAPI(
    title="Task Tracker API",
    description=(
        "Трекер задач: проекты, задачи с тегами и исполнителями, уведомления.\n\n"
        "FastAPI · PostgreSQL + SQLAlchemy + Alembic · JWT + RBAC · Celery + Redis · Docker · CI/CD"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_exception_handler(AppError, app_error_handler)

# Rate limiting (slowapi): 429 при превышении лимита
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS только для явно указанных origin (wildcard запрещён валидатором в config.py)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

for router in (
    health_router,
    auth_router,
    users_router,
    admin_router,
    projects_router,
    tasks_router,
    notifications_router,
):
    app.include_router(router)


@app.get("/", tags=["health"])
def root() -> dict:
    return {"service": "Task Tracker API", "docs": "/docs", "health": "/health"}
