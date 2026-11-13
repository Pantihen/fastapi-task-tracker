import logging

import redis
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


def _check_redis() -> str:
    url = settings.CELERY_BROKER_URL
    if not url.startswith(("redis://", "rediss://")):
        return "skipped"  # в тестах брокер memory://
    try:
        client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        return "ok"
    except redis.RedisError:
        logger.warning("Redis недоступен")
        return "unavailable"


@router.get("/health")
def health(response: Response, db: Session = Depends(get_db)) -> dict:
    """Проверка живости: приложение отвечает, БД и Redis доступны.

    503 — если недоступна база данных (без неё приложение не работает).
    Недоступный Redis даёт статус degraded: REST и GraphQL работают, фоновые задачи — нет.
    """
    try:
        db.execute(text("SELECT 1"))  # константный запрос, без пользовательских данных
        database = "ok"
    except Exception:
        logger.exception("База данных недоступна")
        database = "unavailable"

    redis_status = _check_redis()

    if database != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall = "error"
    elif redis_status == "unavailable":
        overall = "degraded"
    else:
        overall = "ok"

    return {
        "status": overall,
        "database": database,
        "database_backend": db.get_bind().dialect.name,
        "redis": redis_status,
    }
