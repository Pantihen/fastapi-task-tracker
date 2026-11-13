from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "task_tracker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.modules.notifications.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,  # статус STARTED, пока задача выполняется
    result_expires=60 * 60 * 24,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,  # в тестах — без воркера
    task_store_eager_result=True,
    broker_connection_retry_on_startup=True,
)
